# orders/serializers.py
from rest_framework import serializers
from .models import Order, OrderItem, ReturnRequest, ExchangeCode


class OrderItemSerializer(serializers.ModelSerializer):
    product_slug = serializers.SerializerMethodField()
    item_total   = serializers.SerializerMethodField()

    class Meta:
        model  = OrderItem
        fields = [
            'id', 'product_name', 'product_slug', 'variant_label',
            'price', 'quantity', 'image_url', 'item_total',
        ]

    def get_product_slug(self, obj):
        return obj.product.slug if obj.product else ''

    def get_item_total(self, obj):
        return float(obj.price * obj.quantity)


class ExchangeCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ExchangeCode
        fields = ['code', 'original_order_value', 'is_used', 'expires_at', 'notes']


class ReturnRequestSerializer(serializers.ModelSerializer):
    exchange_code = ExchangeCodeSerializer(read_only=True)

    class Meta:
        model  = ReturnRequest
        fields = [
            'id', 'request_type', 'defect_description', 'defect_video_url',
            'status', 'admin_notes', 'exchange_code', 'created_at',
        ]
        read_only_fields = ['status', 'admin_notes', 'exchange_code', 'created_at']


class OrderSerializer(serializers.ModelSerializer):
    items              = OrderItemSerializer(many=True, read_only=True)
    return_requests    = ReturnRequestSerializer(many=True, read_only=True)
    can_request_return = serializers.SerializerMethodField()
    can_cancel         = serializers.SerializerMethodField()
    payment_summary    = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'first_name', 'last_name', 'phone', 'email',
            'shipping_address', 'apartment', 'landmark',
            'city', 'state', 'zip_code', 'country',

            # Product financials (COD charge is NOT in any of these)
            'subtotal', 'discount_amount', 'shipping_fee',
            'tax_amount', 'total_amount',
            'coupon_code', 'exchange_code_used',

            # COD service charge fields
            # advance_amount         = COD upfront charge + 18% GST (paid online)
            # collectible_cod_amount = full product price (paid at delivery)
            # is_partial_cod         = True for all COD orders
            'is_partial_cod',
            'advance_amount',
            'collectible_cod_amount',

            # Status
            'payment_method', 'payment_status', 'order_status',

            # Tracking
            'razorpay_order_id', 'tracking_link', 'tracking_note',
            'delhivery_waybill',

            'accepted_return_policy', 'created_at',

            'items', 'return_requests',
            'can_request_return', 'can_cancel',
            'payment_summary',
        ]

    def get_payment_summary(self, obj):
        """
        Structured payment breakdown consumed by OrderHistory and admin.

        COD example (subtotal ₹33,000):
          product_total          = ₹33,000   (what customer pays at delivery)
          cod_upfront_charge     = ₹660      (2% of subtotal)
          cod_upfront_gst        = ₹118.80   (18% of ₹660)
          paid_online            = ₹778.80   (= advance_amount stored in DB)
          payable_at_delivery    = ₹33,000   (= collectible_cod_amount stored in DB)

        The cod_upfront_gst is derived from advance_amount - (subtotal × 2% / 100)
        so it is always consistent with what was actually charged at checkout.
        """
        if obj.payment_method == 'COD' and obj.is_partial_cod:
            # Derive the breakdown from stored values
            # cod_upfront_charge is stored indirectly; we back-calculate for display.
            # Formula: advance_amount = charge + gst = charge × 1.18
            # So: charge = advance_amount / 1.18
            advance      = float(obj.advance_amount)
            charge       = round(advance / 1.18, 2)
            gst_on_charge = round(advance - charge, 2)

            return {
                'type':                  'COD',
                'label':                 'Cash on Delivery',
                'product_total':         float(obj.total_amount),
                'cod_upfront_charge':    charge,
                'cod_upfront_gst':       gst_on_charge,
                'paid_online':           advance,
                'paid_online_label':     f'₹{advance:,.2f} paid online (COD service charge)',
                'payable_at_delivery':   float(obj.collectible_cod_amount),
                'payable_at_delivery_label': f'₹{obj.collectible_cod_amount:,.2f} to delivery agent',
                'deposit_confirmed':     obj.payment_status in ('Deposit Paid', 'Paid'),
                # Refund note for customer support
                'refund_note':           'The COD service charge is non-refundable.',
            }

        # Online payment
        return {
            'type':                  'Online',
            'label':                 'Online Payment',
            'product_total':         float(obj.total_amount),
            'cod_upfront_charge':    0,
            'cod_upfront_gst':       0,
            'paid_online':           float(obj.total_amount) if obj.payment_status == 'Paid' else 0,
            'paid_online_label':     f'₹{obj.total_amount:,.2f} paid online',
            'payable_at_delivery':   0,
            'payable_at_delivery_label': '',
            'deposit_confirmed':     obj.payment_status == 'Paid',
            'refund_note':           '',
        }

    def get_can_request_return(self, obj):
        from django.utils import timezone
        if obj.order_status != 'Delivered':
            return False
        if not obj.accepted_return_policy:
            return False
        if (timezone.now() - obj.updated_at).days > 15:
            return False
        if obj.return_requests.filter(status='Pending').exists():
            return False
        return True

    def get_can_cancel(self, obj):
        return obj.order_status in ('Pending', 'Processing')