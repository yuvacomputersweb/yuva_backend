# orders/views.py
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination

from .models import Order, OrderItem, ReturnRequest, ExchangeCode
from .serializers import OrderSerializer, ReturnRequestSerializer
from store.models import Product, ProductVariant, SiteConfig, Coupon
from accounts.models import SavedAddress
from payments.razorpay_client import create_order as razorpay_create_order, _get_client

# ── Fixed 18% GST on COD service charge ──────────────────────────────────────
# This is separate from product GST (siteConfig.tax_percentage).
# It is a government-mandated service charge GST, always 18%.
COD_SERVICE_GST_PCT = Decimal('18')


class OrderPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 20


class OrderListView(generics.ListAPIView):
    serializer_class   = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class   = OrderPagination

    def get_queryset(self):
        return Order.objects.filter(
            user=self.request.user
        ).prefetch_related('items', 'return_requests__exchange_code').order_by('-created_at')


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def order_detail(request, pk):
    try:
        order = Order.objects.prefetch_related(
            'items', 'return_requests__exchange_code'
        ).get(pk=pk, user=request.user)
        return Response(OrderSerializer(order).data)
    except Order.DoesNotExist:
        return Response({'error': 'Order not found'}, status=404)


class CheckoutView(APIView):
    """
    COD charge logic (correct business spec):

      Product Total  = subtotal - discounts + shipping + product_tax
                     = stored in total_amount  (UNCHANGED — no COD added)

      COD Upfront    = 2% × subtotal           (service charge rate)
      COD GST        = 18% × COD Upfront       (fixed, not product GST)
      Paid Online    = COD Upfront + COD GST   → stored in advance_amount
      Paid at Door   = total_amount            → stored in collectible_cod_amount

    The COD charge is NON-REFUNDABLE. It is never part of total_amount.
    Exchange codes use total_amount only. Refunds on cancellation return
    advance_amount only (service fee), never the product price (not collected).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data                  = request.data
        cart_items            = data.get('items', [])
        payment_method        = data.get('payment_method', 'Online')
        coupon_code           = data.get('coupon_code', '').strip().upper()
        exchange_code_input   = data.get('exchange_code', '').strip().upper()
        save_as_default       = data.get('save_as_default', False)
        accepted_return_policy = data.get('accepted_return_policy', False)

        if not cart_items:
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        # ── 1. Site config ────────────────────────────────────────────────────
        config         = SiteConfig.objects.first()
        shipping_flat  = Decimal(str(config.shipping_fee)) if config else Decimal('0')
        free_threshold = Decimal(str(config.free_shipping_threshold)) if config else Decimal('0')
        cod_charge_pct = Decimal(str(config.cod_surcharge_percentage)) if config else Decimal('2')
        tax_pct        = Decimal(str(config.tax_percentage)) if config else Decimal('0')

        try:
            with transaction.atomic():
                # ── 2. Validate cart & build line items ───────────────────────
                order_line_items = []
                subtotal         = Decimal('0.00')

                for item in cart_items:
                    variant_id = item.get('variant_id')
                    product_id = item.get('product_id')
                    quantity   = int(item.get('quantity', 1))

                    if variant_id:
                        variant       = ProductVariant.objects.select_for_update().get(id=variant_id)
                        product       = variant.product
                        server_price  = product.price + variant.price_override
                        parts         = [p for p in [variant.processor, variant.ram, variant.storage] if p]
                        variant_label = ' / '.join(parts)
                        if variant.stock < quantity:
                            return Response(
                                {'error': f'Insufficient stock for {product.title} ({variant_label})'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        product       = Product.objects.get(id=product_id)
                        variant       = None
                        server_price  = product.price
                        variant_label = ''

                    subtotal += server_price * quantity
                    primary_img = product.images.filter(is_primary=True).first() or product.images.first()
                    img_url     = request.build_absolute_uri(primary_img.image.url) if primary_img else ''

                    order_line_items.append({
                        'product':       product,
                        'variant':       variant,
                        'product_name':  product.title,
                        'variant_label': variant_label,
                        'price':         server_price,
                        'quantity':      quantity,
                        'image_url':     img_url,
                    })

                # ── 3. Coupon ─────────────────────────────────────────────────
                discount_amount = Decimal('0.00')
                coupon_obj      = None

                if coupon_code:
                    try:
                        coupon = Coupon.objects.get(code=coupon_code, active=True)
                        now    = timezone.now()
                        if coupon.valid_from > now or coupon.valid_to < now:
                            return Response({'error': 'Coupon has expired'}, status=400)
                        if coupon.uses_count >= coupon.usage_limit:
                            return Response({'error': 'Coupon usage limit reached'}, status=400)
                        if subtotal < coupon.min_order_value:
                            return Response(
                                {'error': f'Minimum order of ₹{coupon.min_order_value} required'},
                                status=400
                            )
                        if coupon.first_order_only and Order.objects.filter(
                            user=request.user, payment_status__in=['Paid', 'Deposit Paid']
                        ).exists():
                            return Response({'error': 'This coupon is only for your first order'}, status=400)
                        discount_amount = (
                            (subtotal * coupon.value / 100)
                            if coupon.discount_type == 'percentage'
                            else coupon.value
                        )
                        coupon_obj = coupon
                    except Coupon.DoesNotExist:
                        return Response({'error': 'Invalid coupon code'}, status=400)

                # ── 4. Exchange code ──────────────────────────────────────────
                # Exchange value is based on product price (total_amount) only.
                # COD advance is never included in exchange calculations.
                exchange_obj      = None
                exchange_discount = Decimal('0.00')

                if exchange_code_input:
                    try:
                        exchange_obj = ExchangeCode.objects.get(
                            code=exchange_code_input, is_used=False
                        )
                        if exchange_obj.expires_at and exchange_obj.expires_at < timezone.now():
                            return Response({'error': 'Exchange code has expired'}, status=400)
                        if subtotal < exchange_obj.original_order_value:
                            return Response(
                                {'error': f'New order must be at least ₹{exchange_obj.original_order_value}'},
                                status=400
                            )
                        exchange_discount = exchange_obj.original_order_value
                    except ExchangeCode.DoesNotExist:
                        return Response({'error': 'Invalid or already used exchange code'}, status=400)

                # ── 5. Product financials (no COD charge here) ────────────────
                taxable      = max(Decimal('0'), subtotal - discount_amount - exchange_discount)
                tax_amount   = (taxable * tax_pct / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                shipping_fee = (
                    Decimal('0.00')
                    if (free_threshold > 0 and subtotal >= free_threshold)
                    else shipping_flat
                )
                # total_amount = full product cost, always.
                # For COD this is what the customer pays AT THE DOOR.
                # For Online this is what Razorpay charges now.
                # COD service charge is NEVER added to this number.
                total_amount = (taxable + tax_amount + shipping_fee).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP
                )

                # ── 6. COD service charge (separate, non-product) ─────────────
                #
                # Correct formula:
                #   cod_upfront_charge = 2% × subtotal   (gross product value before discounts)
                #   cod_upfront_gst    = 18% × cod_upfront_charge
                #   advance_amount     = cod_upfront_charge + cod_upfront_gst
                #                        ← Razorpay charges THIS amount now
                #   collectible_cod_amount = total_amount
                #                        ← delivery agent collects THIS at the door
                #
                # advance_amount is NON-REFUNDABLE (service fee).
                # Exchange and return calculations use total_amount only.

                is_partial_cod         = payment_method == 'COD'
                cod_upfront_charge     = Decimal('0.00')
                cod_upfront_gst        = Decimal('0.00')
                advance_amount         = Decimal('0.00')
                collectible_cod_amount = Decimal('0.00')

                if is_partial_cod:
                    cod_upfront_charge = (subtotal * cod_charge_pct / 100).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
                    cod_upfront_gst = (cod_upfront_charge * COD_SERVICE_GST_PCT / 100).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
                    advance_amount         = cod_upfront_charge + cod_upfront_gst
                    collectible_cod_amount = total_amount  # unchanged product price

                # ── 7. Address fields ─────────────────────────────────────────
                first_name = data.get('first_name', '')
                last_name  = data.get('last_name', '')
                phone      = data.get('phone', '')
                address    = data.get('address', '')
                apartment  = data.get('apartment', '')
                landmark   = data.get('landmark', '')
                city       = data.get('city', '')
                state_val  = data.get('state', '')
                zip_code   = data.get('zip_code', '')
                country    = data.get('country', 'India')

                # ── 8. Create order record ────────────────────────────────────
                order = Order.objects.create(
                    user=request.user,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    email=request.user.email,
                    shipping_address=address,
                    apartment=apartment,
                    landmark=landmark,
                    city=city,
                    state=state_val,
                    zip_code=zip_code,
                    country=country,
                    subtotal=subtotal,
                    discount_amount=discount_amount + exchange_discount,
                    shipping_fee=shipping_fee,
                    cod_fee=Decimal('0.00'),     # legacy — always 0
                    tax_amount=tax_amount,
                    total_amount=total_amount,   # product value only
                    coupon_code=coupon_code,
                    exchange_code_used=exchange_code_input,
                    payment_method=payment_method,
                    payment_status='Pending',
                    order_status='Pending',
                    accepted_return_policy=accepted_return_policy,
                    is_partial_cod=is_partial_cod,
                    advance_amount=advance_amount,             # COD charge + GST
                    collectible_cod_amount=collectible_cod_amount,  # product price at delivery
                )

                for item in order_line_items:
                    OrderItem.objects.create(
                        order=order,
                        product=item['product'],
                        variant=item['variant'],
                        product_name=item['product_name'],
                        variant_label=item['variant_label'],
                        price=item['price'],
                        quantity=item['quantity'],
                        image_url=item['image_url'],
                    )

                if exchange_obj:
                    exchange_obj.is_used = True
                    exchange_obj.used_at = timezone.now()
                    exchange_obj.save()

                if save_as_default and address:
                    SavedAddress.objects.filter(user=request.user, is_default=True).update(is_default=False)
                    SavedAddress.objects.create(
                        user=request.user, label='Home',
                        first_name=first_name, last_name=last_name,
                        address=address, apartment=apartment, landmark=landmark,
                        city=city, state=state_val, zip_code=zip_code,
                        country=country, phone=phone, is_default=True,
                    )

                if coupon_obj:
                    coupon_obj.uses_count += 1
                    coupon_obj.save()

                # ── 9. Razorpay order ─────────────────────────────────────────
                if payment_method == 'COD':
                    # Charge ONLY the COD service charge + GST now.
                    # Product price is NOT collected online.
                    rzp_order = razorpay_create_order(advance_amount)
                    order.razorpay_order_id = rzp_order['id']
                    order.save(update_fields=['razorpay_order_id'])

                    return Response({
                        'order_id':               order.id,
                        'payment_method':         'COD',
                        'razorpay_order_id':      rzp_order['id'],
                        'amount':                 rzp_order['amount'],  # paise for Razorpay SDK
                        'currency':               'INR',
                        'key':                    settings.RAZORPAY_KEY_ID,
                        # Full breakdown for checkout UI
                        'product_total':          float(total_amount),
                        'cod_upfront_charge':     float(cod_upfront_charge),
                        'cod_upfront_gst':        float(cod_upfront_gst),
                        'advance_amount':         float(advance_amount),
                        'collectible_cod_amount': float(collectible_cod_amount),
                        'message': (
                            f'Pay ₹{advance_amount} now (COD service + GST). '
                            f'Pay ₹{collectible_cod_amount} to delivery agent.'
                        ),
                    }, status=status.HTTP_201_CREATED)

                # Online: charge full product total now
                rzp_order = razorpay_create_order(total_amount)
                order.razorpay_order_id = rzp_order['id']
                order.save(update_fields=['razorpay_order_id'])

                return Response({
                    'order_id':          order.id,
                    'razorpay_order_id': rzp_order['id'],
                    'amount':            rzp_order['amount'],
                    'currency':          'INR',
                    'key':               settings.RAZORPAY_KEY_ID,
                    'payment_method':    'Online',
                }, status=status.HTTP_201_CREATED)

        except (ProductVariant.DoesNotExist, Product.DoesNotExist):
            return Response({'error': 'Product not found'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CancelOrderView(APIView):
    """
    Cancellation refund rules:
    - Online (Paid):       refund total_amount (full product price)
    - COD (Deposit Paid):  refund advance_amount (COD service charge only)
                           Product was never charged online → nothing else to refund
    COD advance_amount is technically non-refundable (service fee),
    but this implementation refunds it on pre-dispatch cancellation.
    Adjust to not refund if business policy changes.
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            order = Order.objects.select_for_update().get(pk=pk, user=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=404)

        if order.order_status not in ('Pending', 'Processing'):
            return Response(
                {'error': f'Cannot cancel an order with status: {order.order_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Restore stock
        for item in order.items.select_related('variant').all():
            if item.variant:
                item.variant.stock += item.quantity
                item.variant.save()

        refund_initiated = False
        refund_amount    = Decimal('0.00')

        if order.payment_status in ('Paid', 'Deposit Paid') and order.razorpay_payment_id:
            try:
                client = _get_client()
                refund_amount = (
                    order.advance_amount   # COD: only the service charge was paid online
                    if order.payment_status == 'Deposit Paid'
                    else order.total_amount  # Online: full product price
                )
                client.payment.refund(
                    order.razorpay_payment_id,
                    {'amount': int(refund_amount * 100)}
                )
                order.payment_status = 'Refunded'
                refund_initiated     = True
            except Exception:
                order.payment_status = 'Refund Pending'

        order.order_status = 'Cancelled'
        order.save()

        return Response({
            'message':          'Order cancelled successfully.',
            'refund_initiated': refund_initiated,
            'refund_amount':    float(refund_amount),
            'note': (
                f'Refund of ₹{refund_amount} (COD service charge) will reflect in 5–7 days.'
                if refund_initiated and order.is_partial_cod
                else f'Refund of ₹{refund_amount} will reflect in 5–7 business days.'
                if refund_initiated
                else 'No payment was collected online — no refund needed.'
            ),
        })


class ReturnRequestCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, user=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=404)

        if order.order_status != 'Delivered':
            return Response({'error': 'Only delivered orders can be returned'}, status=400)
        if not order.accepted_return_policy:
            return Response({'error': 'Return policy was not accepted at checkout'}, status=400)
        if not order.delivered_at:
            return Response({'error': 'Delivery date not recorded'}, status=400)
        if (timezone.now() - order.delivered_at).days > 15:
            return Response({'error': 'Return window of 15 days has expired'}, status=400)
        if order.return_requests.filter(status='Pending').exists():
            return Response({'error': 'A return request is already pending'}, status=400)

        serializer = ReturnRequestSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(order=order, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=400)


class ValidateExchangeCodeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').strip().upper()
        try:
            exchange = ExchangeCode.objects.get(code=code, is_used=False)
            if exchange.expires_at and exchange.expires_at < timezone.now():
                return Response({'valid': False, 'error': 'Exchange code has expired'}, status=400)
            return Response({
                'valid':                True,
                'code':                 exchange.code,
                'original_order_value': float(exchange.original_order_value),
                'message':              f'Code valid! Min new order: ₹{exchange.original_order_value}',
            })
        except ExchangeCode.DoesNotExist:
            return Response({'valid': False, 'error': 'Invalid or already used exchange code'}, status=400)

class TrackOrderView(APIView):
    """
    Public order tracking: GET /api/orders/track/?order_id=123&phone=9876543210

    The phone number must match the order (last 10 digits), so order ids
    can't be used to look up other customers' orders.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        import re
        from .tracking import fetch_tracking

        order_id = re.sub(r"\D", "", request.query_params.get("order_id", ""))
        phone = re.sub(r"\D", "", request.query_params.get("phone", ""))[-10:]
        if not order_id or len(phone) != 10:
            return Response({"error": "Enter your order number and the 10-digit phone number used at checkout."}, status=400)

        order = Order.objects.prefetch_related("items").filter(pk=order_id).first()
        if not order or re.sub(r"\D", "", order.phone or "")[-10:] != phone:
            return Response({"error": "We couldn't find an order with that number and phone."}, status=404)

        courier = fetch_tracking(order.delhivery_waybill) if order.delhivery_waybill else None
        return Response({
            "order_id": order.id,
            "placed_at": order.created_at,
            "order_status": order.order_status,
            "payment_method": order.payment_method,
            "payment_status": order.payment_status,
            "total_amount": order.total_amount,
            "amount_due_on_delivery": order.collectible_cod_amount if order.payment_method == "COD" else 0,
            "delivered_at": order.delivered_at,
            "city": order.city,
            "items": [
                {"name": i.product_name, "variant": i.variant_label, "quantity": i.quantity}
                for i in order.items.all()
            ],
            "waybill": order.delhivery_waybill,
            "tracking_link": order.tracking_link,
            "tracking_note": order.tracking_note,
            "courier": courier,
        })
