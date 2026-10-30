# payments/views.py
import json
import logging
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import AllowAny

from orders.models import Order
from .razorpay_client import verify_payment_signature, _get_client

logger = logging.getLogger(__name__)


def _trigger_logistics(order) -> None:
    from .confirm import trigger_logistics
    trigger_logistics(order)


class VerifyPaymentView(APIView):
    """
    Handles payment verification for TWO scenarios:
      1. Online orders  → full total_amount paid → payment_status = 'Paid'
      2. COD orders     → 2% advance_amount paid  → payment_status = 'Deposit Paid'

    Both paths deduct stock and trigger Delhivery + WhatsApp.
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        data           = request.data
        rzp_order_id   = data.get('razorpay_order_id')
        rzp_payment_id = data.get('razorpay_payment_id')
        rzp_signature  = data.get('razorpay_signature')

        try:
            order = Order.objects.select_for_update().get(razorpay_order_id=rzp_order_id)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        # Idempotency: already processed
        if order.payment_status in ('Paid', 'Deposit Paid'):
            return Response({'message': 'Already processed'}, status=status.HTTP_200_OK)

        # Verify Razorpay signature
        is_valid = verify_payment_signature(rzp_order_id, rzp_payment_id, rzp_signature)
        if not is_valid:
            order.payment_status = 'Failed'
            order.save(update_fields=['payment_status'])
            return Response({'error': 'Invalid payment signature'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Deduct stock (same logic for both COD deposit and Online full pay) ──
        for item in order.items.select_related('variant__product').all():
            if item.variant:
                item.variant.take_stock(item.quantity)

        # ── Set payment and order status based on payment method ──────────────
        order.razorpay_payment_id = rzp_payment_id
        order.order_status        = 'Processing'

        if order.is_partial_cod:
            # COD: 2% deposit paid — remaining 98% collected on delivery
            order.payment_status = 'Deposit Paid'
            logger.info(
                f"[Payments] COD deposit verified for Order #{order.id} | "
                f"Advance: ₹{order.advance_amount} | "
                f"Due on delivery: ₹{order.collectible_cod_amount}"
            )
        else:
            # Online: full amount paid
            order.payment_status = 'Paid'
            logger.info(f"[Payments] Full payment verified for Order #{order.id} | ₹{order.total_amount}")

        order.save()

        # ── Fire Delhivery + WhatsApp after DB commit ─────────────────────────
        _trigger_logistics(order)

        # ── Build response with payment summary ───────────────────────────────
        if order.is_partial_cod:
            return Response({
                'message':                'Deposit paid successfully! Your COD order is confirmed.',
                'payment_status':         'Deposit Paid',
                'advance_paid':           float(order.advance_amount),
                'amount_due_on_delivery': float(order.collectible_cod_amount),
                'total_amount':           float(order.total_amount),
            }, status=status.HTTP_200_OK)

        return Response({
            'message':        'Payment verified successfully',
            'payment_status': 'Paid',
            'total_amount':   float(order.total_amount),
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class RazorpayWebhookView(APIView):
    """
    Razorpay webhook handler — covers cases where frontend verification
    was missed (e.g. browser crash after payment).
    Idempotent: services.py guards against duplicate Delhivery/WhatsApp calls.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', None)
        if not webhook_secret:
            return Response({'error': 'Webhook not configured'}, status=500)

        webhook_sig = request.headers.get('X-Razorpay-Signature')
        try:
            client = _get_client()
            client.utility.verify_webhook_signature(
                request.body.decode('utf-8'),
                webhook_sig,
                webhook_secret,
            )
        except Exception as e:
            logger.error(f"Webhook signature failed: {e}")
            return Response({'error': 'Invalid signature'}, status=400)

        data           = json.loads(request.body)
        event          = data.get('event')
        entity         = data.get('payload', {}).get('payment', {}).get('entity', {})
        rzp_order_id   = entity.get('order_id')
        rzp_payment_id = entity.get('id')

        try:
            order = Order.objects.get(razorpay_order_id=rzp_order_id)

            if event == 'payment.captured':
                from .confirm import confirm_paid_order
                confirm_paid_order(order, rzp_payment_id)

            elif event == 'payment.failed' and order.payment_status not in ('Paid', 'Deposit Paid'):
                order.payment_status = 'Failed'
                order.save(update_fields=['payment_status'])

        except Order.DoesNotExist:
            pass

        return Response({'status': 'handled'})
