# orders/models.py
from decimal import Decimal
from django.db import models
from django.conf import settings
from store.models import Product, ProductVariant
import uuid
from django.utils import timezone
from django.dispatch import receiver
from datetime import timedelta
from django.db.models.signals import post_save


class Order(models.Model):
    PAYMENT_STATUS = [
        ('Pending', 'Pending'),
        ('Deposit Paid', 'Deposit Paid'),   # ← NEW: 2% advance paid for COD
        ('Paid', 'Paid'),
        ('Failed', 'Failed'),
        ('Refunded', 'Refunded'),
        ('Refund Pending', 'Refund Pending'),
    ]
    ORDER_STATUS = [
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Confirmed', 'Confirmed'),
        ('Shipped', 'Shipped'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
    ]
    PAYMENT_METHOD = [
        ('Online', 'Online'),
        ('COD', 'Cash on Delivery'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders'
    )
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    exchange_code_used = models.CharField(max_length=20, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Shipping
    shipping_address = models.TextField()
    apartment = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, default='India')

    # Financials
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    coupon_code = models.CharField(max_length=50, blank=True)

    # ── Partial COD payment fields ────────────────────────────────────────────
    # advance_amount       = 2% of total_amount, paid online via Razorpay at checkout
    # collectible_cod_amount = remaining 98%, collected by delivery agent on delivery
    # is_partial_cod       = True only for COD orders (flag for easy filtering)
    # cod_fee              = kept for backwards compatibility, always 0 now (surcharge removed)
    cod_fee = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text="Legacy field — kept for DB compatibility. Always 0 now."
    )
    advance_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="2% of total_amount paid online via Razorpay at checkout (COD orders only)"
    )
    collectible_cod_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text="Amount collected on delivery = total_amount - advance_amount (COD orders only)"
    )
    is_partial_cod = models.BooleanField(
        default=False,
        help_text="True for COD orders that require 2% upfront deposit"
    )

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD, default='Online')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='Pending')
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS, default='Pending')

    # Policy acceptance
    accepted_return_policy = models.BooleanField(
        default=True,
        help_text="Customer accepted 15-day exchange policy at checkout"
    )

    # Razorpay
    razorpay_order_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)

    # Tracking
    tracking_link = models.URLField(max_length=500, blank=True, null=True)
    tracking_note = models.TextField(blank=True, null=True)

    # Logistics & Notifications
    delhivery_waybill = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Auto-filled waybill ID from Delhivery after shipment creation"
    )
    whatsapp_sent = models.BooleanField(
        default=False,
        help_text="True once the 'Order Placed' WhatsApp message has been sent"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} — {self.user.email}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(
        'store.Product', on_delete=models.SET_NULL, null=True, blank=True
    )
    variant = models.ForeignKey(
        'store.ProductVariant', on_delete=models.SET_NULL, null=True, blank=True
    )
    product_name = models.CharField(max_length=255)
    variant_label = models.CharField(max_length=100, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)
    image_url = models.TextField(blank=True)

    def __str__(self):
        return f"{self.product_name} x{self.quantity}"

    @property
    def total(self):
        return self.price * self.quantity


class ExchangeCode(models.Model):
    code = models.CharField(
        max_length=20, unique=True,
        help_text="Unique code given to customer for exchange/upgrade"
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='exchange_codes')
    original_order_value = models.DecimalField(max_digits=10, decimal_places=2)
    is_used = models.BooleanField(default=False)
    used_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = f"YC-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} (Order #{self.order.id})"


class ReturnRequest(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending Review'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    TYPE_CHOICES = [
        ('Exchange', 'Exchange (Same Value)'),
        ('Upgrade', 'Upgrade (Higher Value)'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='return_requests')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='Exchange')
    defect_description = models.TextField()
    defect_video_url = models.URLField(max_length=1000, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    admin_notes = models.TextField(blank=True)
    exchange_code = models.OneToOneField(
        ExchangeCode, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='return_request'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Return #{self.id} — Order #{self.order.id} [{self.status}]"


from datetime import timedelta


@receiver(post_save, sender=ReturnRequest)
def create_exchange_code_on_approval(sender, instance, created, **kwargs):
    if instance.status == 'Approved' and not instance.exchange_code:
        if not ExchangeCode.objects.filter(order=instance.order).exists():
            code = ExchangeCode.objects.create(
                order=instance.order,
                original_order_value=instance.order.total_amount,
                expires_at=timezone.now() + timedelta(days=30),
                notes=f"Auto-generated for return #{instance.id}"
            )
            instance.exchange_code = code
            instance.save(update_fields=['exchange_code'])


class OrderNotification(models.Model):
    """One WhatsApp message sent (or attempted) to a customer about an order."""
    EVENT_CHOICES = [
        ('order_placed', 'Order placed'),
        ('payment_received', 'Payment received'),
        ('order_shipped', 'Shipped'),
        ('out_for_delivery', 'Out for delivery'),
        ('order_delivered', 'Delivered'),
        ('order_cancelled', 'Cancelled'),
    ]
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notifications')
    event = models.CharField(max_length=30, choices=EVENT_CHOICES)
    template = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    success = models.BooleanField(default=False)
    response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.order_id} {self.get_event_display()} — {'sent' if self.success else 'failed'}"


# ── Status-change WhatsApp messages ───────────────────────────────────────────
# Fires for every save path: admin form, admin list edits, the Delhivery sync
# command and the shell. Messages go out after the transaction commits so a
# rolled-back save never notifies a customer.
from django.db import transaction
from django.db.models.signals import pre_save

_STATUS_EVENTS = {
    'Shipped': 'order_shipped',
    'Delivered': 'order_delivered',
    'Cancelled': 'order_cancelled',
}


@receiver(pre_save, sender=Order)
def _remember_previous_status(sender, instance, **kwargs):
    if instance.pk:
        previous = sender.objects.filter(pk=instance.pk).values('order_status', 'payment_status').first() or {}
    else:
        previous = {}
    instance._previous_order_status = previous.get('order_status')
    instance._previous_payment_status = previous.get('payment_status')


@receiver(post_save, sender=Order)
def _notify_on_status_change(sender, instance, created, **kwargs):
    from .notifications import notify

    events = []
    old_status = getattr(instance, '_previous_order_status', None)
    if not created and instance.order_status != old_status and instance.order_status in _STATUS_EVENTS:
        events.append(_STATUS_EVENTS[instance.order_status])

    old_payment = getattr(instance, '_previous_payment_status', None)
    if not created and instance.payment_status != old_payment and instance.payment_status in ('Paid', 'Deposit Paid'):
        events.append('payment_received')

    if instance.order_status == 'Delivered' and not instance.delivered_at:
        sender.objects.filter(pk=instance.pk).update(delivered_at=timezone.now())

    for event in events:
        transaction.on_commit(lambda e=event: notify(instance, e))

