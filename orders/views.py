#order/views
from decimal import Decimal
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


class OrderPagination(PageNumberPagination):
    page_size = 5
    page_size_query_param = 'page_size'
    max_page_size = 20


class OrderListView(generics.ListAPIView):
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = OrderPagination

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
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        data = request.data
        cart_items = data.get('items', [])
        payment_method = data.get('payment_method', 'Online')
        coupon_code = data.get('coupon_code', '').strip().upper()
        exchange_code_input = data.get('exchange_code', '').strip().upper()
        save_as_default = data.get('save_as_default', False)
        accepted_return_policy = data.get('accepted_return_policy', False)

        if not cart_items:
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        # ── 1. Site config ───────────────────────────────────────────────────
        config = SiteConfig.objects.first()
        shipping_flat = Decimal(str(config.shipping_fee)) if config else Decimal('0')
        free_threshold = Decimal(str(config.free_shipping_threshold)) if config else Decimal('0')
        cod_pct = Decimal(str(config.cod_surcharge_percentage)) if config else Decimal('2')
        tax_pct = Decimal(str(config.tax_percentage)) if config else Decimal('0')

        # ── Start Transaction Block ──
        # We wrap the entire logic in atomic() to support select_for_update()
        try:
            with transaction.atomic():
                # ── 2. Validate cart & build line items ──────────────────────────────
                order_line_items = []
                subtotal = Decimal('0.00')

                for item in cart_items:
                    variant_id = item.get('variant_id')
                    product_id = item.get('product_id')
                    quantity = int(item.get('quantity', 1))

                    if variant_id:
                        # select_for_update() is now legally inside a transaction[cite: 1]
                        variant = ProductVariant.objects.select_for_update().get(id=variant_id)
                        product = variant.product
                        server_price = product.price + variant.price_override
                        variant_label = f"{variant.ram} / {variant.storage}"
                        if variant.stock < quantity:
                            return Response(
                                {'error': f'Insufficient stock for {product.title} ({variant_label})'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                    else:
                        product = Product.objects.get(id=product_id)
                        variant = None
                        server_price = product.price
                        variant_label = ''

                    subtotal += server_price * quantity
                    primary_img = product.images.filter(is_primary=True).first() or product.images.first()
                    img_url = request.build_absolute_uri(primary_img.image.url) if primary_img else ''

                    order_line_items.append({
                        'product': product,
                        'variant': variant,
                        'product_name': product.title,
                        'variant_label': variant_label,
                        'price': server_price,
                        'quantity': quantity,
                        'image_url': img_url,
                    })

                # ── 3. Coupon ────────────────────────────────────────────────────────
                discount_amount = Decimal('0.00')
                coupon_obj = None

                if coupon_code:
                    try:
                        coupon = Coupon.objects.get(code=coupon_code, active=True)
                        now = timezone.now()
                        if coupon.valid_from > now or coupon.valid_to < now:
                            return Response({'error': 'Coupon has expired'}, status=status.HTTP_400_BAD_REQUEST)
                        if coupon.uses_count >= coupon.usage_limit:
                            return Response({'error': 'Coupon usage limit reached'}, status=status.HTTP_400_BAD_REQUEST)
                        if subtotal < coupon.min_order_value:
                            return Response(
                                {'error': f'Minimum order of ₹{coupon.min_order_value} required'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        if coupon.discount_type == 'percentage':
                            discount_amount = (subtotal * coupon.value) / 100
                        else:
                            discount_amount = coupon.value
                        coupon_obj = coupon
                    except Coupon.DoesNotExist:
                        return Response({'error': 'Invalid coupon code'}, status=status.HTTP_400_BAD_REQUEST)

                # ── 4. Exchange code ─────────────────────────────────────────────────
                exchange_obj = None
                exchange_discount = Decimal('0.00')

                if exchange_code_input:
                    try:
                        exchange_obj = ExchangeCode.objects.get(code=exchange_code_input, is_used=False)
                        if exchange_obj.expires_at and exchange_obj.expires_at < timezone.now():
                            return Response({'error': 'Exchange code has expired'}, status=status.HTTP_400_BAD_REQUEST)
                        if subtotal < exchange_obj.original_order_value:
                            return Response(
                                {'error': f'New order must be at least ₹{exchange_obj.original_order_value} (equal or higher value exchange only)'},
                                status=status.HTTP_400_BAD_REQUEST
                            )
                        exchange_discount = exchange_obj.original_order_value
                    except ExchangeCode.DoesNotExist:
                        return Response({'error': 'Invalid or already used exchange code'}, status=status.HTTP_400_BAD_REQUEST)

                # ── 5. Fee calculations ──────────────────────────────────────────────
                taxable = max(Decimal('0'), subtotal - discount_amount - exchange_discount)
                tax_amount = (taxable * tax_pct) / 100
                shipping_fee = Decimal('0.00') if (free_threshold > 0 and subtotal >= free_threshold) else shipping_flat
                cod_fee = (subtotal * cod_pct / 100) if payment_method == 'COD' else Decimal('0.00')
                total_amount = taxable + tax_amount + shipping_fee + cod_fee

                # ── 6. Shipping address ──────────────────────────────────────────────
                first_name = data.get('first_name', '')
                last_name = data.get('last_name', '')
                phone = data.get('phone', '')
                address = data.get('address', '')
                apartment = data.get('apartment', '')
                landmark = data.get('landmark', '')
                city = data.get('city', '')
                state = data.get('state', '')
                zip_code = data.get('zip_code', '')
                country = data.get('country', 'India')

                # ── 7. Create order ──────────────────────────────────────────────────
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
                    state=state,
                    zip_code=zip_code,
                    country=country,
                    subtotal=subtotal,
                    discount_amount=discount_amount + exchange_discount,
                    shipping_fee=shipping_fee,
                    cod_fee=cod_fee,
                    tax_amount=tax_amount,
                    total_amount=total_amount,
                    coupon_code=coupon_code,
                    exchange_code_used=exchange_code_input,
                    payment_method=payment_method,
                    payment_status='Pending',
                    order_status='Processing' if payment_method == 'COD' else 'Pending',
                    accepted_return_policy=accepted_return_policy,
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
                    if payment_method == 'COD' and item['variant']:
                        v = item['variant']
                        v.stock -= item['quantity']
                        v.save()

                if exchange_obj:
                    exchange_obj.is_used = True
                    exchange_obj.used_at = timezone.now()
                    exchange_obj.save()

                if save_as_default:
                    SavedAddress.objects.filter(user=request.user, is_default=True).update(is_default=False)
                    SavedAddress.objects.create(
                        user=request.user, label='Home', first_name=first_name, last_name=last_name,
                        address=address, apartment=apartment, landmark=landmark, city=city,
                        state=state, zip_code=zip_code, country=country, phone=phone, is_default=True,
                    )

                if coupon_obj:
                    coupon_obj.uses_count += 1
                    coupon_obj.save()

                if payment_method == 'COD':
                    return Response({
                        'order_id': order.id,
                        'payment_method': 'COD',
                        'message': 'Order placed! Our team will contact you.',
                        'total_amount': float(total_amount),
                    }, status=status.HTTP_201_CREATED)

                # Online — Razorpay order
                rzp_order = razorpay_create_order(total_amount)
                order.razorpay_order_id = rzp_order['id']
                order.save()

                return Response({
                    'order_id': order.id,
                    'razorpay_order_id': rzp_order['id'],
                    'amount': rzp_order['amount'],
                    'currency': 'INR',
                    'key': settings.RAZORPAY_KEY_ID,
                    'payment_method': 'Online',
                }, status=status.HTTP_201_CREATED)

        except (ProductVariant.DoesNotExist, Product.DoesNotExist):
            return Response({'error': 'Product not found'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Atomic block ensures DB rollbacks if third-party APIs (Razorpay) or code fails[cite: 1]
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CancelOrderView(APIView):
    """
    Customer cancels order before it's Confirmed.
    If paid online, Razorpay refund is initiated automatically.
    """
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            order = Order.objects.select_for_update().get(pk=pk, user=request.user)
        except Order.DoesNotExist:
            return Response({'error': 'Order not found'}, status=404)

        # Only allow cancel if order hasn't been confirmed yet
        if order.order_status not in ('Pending', 'Processing'):
            return Response(
                {'error': f'Cannot cancel an order that is already {order.order_status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Restore stock
        for item in order.items.select_related('variant').all():
            if item.variant:
                item.variant.stock += item.quantity
                item.variant.save()

        # If paid online, initiate Razorpay refund
        refund_initiated = False
        if order.payment_status == 'Paid' and order.razorpay_payment_id:
            try:
                client = _get_client()
                amount_paise = int(order.total_amount * 100)
                client.payment.refund(order.razorpay_payment_id, {'amount': amount_paise})
                order.payment_status = 'Refunded'
                refund_initiated = True
            except Exception as e:
                # Don't block cancellation if refund API fails — admin can do it manually
                order.payment_status = 'Refund Pending'

        order.order_status = 'Cancelled'
        order.save()
        

        return Response({
            'message': 'Order cancelled successfully.',
            'refund_initiated': refund_initiated,
            'note': 'Refund will reflect in 5-7 business days.' if refund_initiated else (
                'No payment was made — no refund needed.' if order.payment_method == 'COD' else
                'Refund could not be processed automatically. Please contact support.'
            )
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
         return Response({'error': 'Order not yet delivered'}, status=400)

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
                'valid': True,
                'code': exchange.code,
                'original_order_value': float(exchange.original_order_value),
                'message': f'Code valid! Min new order: ₹{exchange.original_order_value}',
            })
        except ExchangeCode.DoesNotExist:
            return Response({'valid': False, 'error': 'Invalid or already used exchange code'}, status=400)
