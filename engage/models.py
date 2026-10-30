from django.conf import settings
from django.db import models


class WhatsAppMessage(models.Model):
    """Log of every non-order WhatsApp message (alerts, reminders, summaries)."""
    KIND_CHOICES = [
        ('back_in_stock', 'Back in stock'),
        ('cart_reminder', 'Cart reminder'),
        ('low_stock', 'Low-stock alert'),
        ('daily_summary', 'Daily summary'),
        ('new_lead', 'New lead alert'),
        ('return_update', 'Return / replacement update'),
    ]
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    phone = models.CharField(max_length=20)
    template = models.CharField(max_length=100)
    params = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=False)
    response = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'WhatsApp message'

    def __str__(self):
        return f"{self.get_kind_display()} → {self.phone} ({'sent' if self.success else 'failed'})"


class StockAlert(models.Model):
    """A customer asked to be told on WhatsApp when a sold-out laptop is back."""
    product = models.ForeignKey('store.Product', on_delete=models.CASCADE, related_name='stock_alerts')
    variant = models.ForeignKey(
        'store.ProductVariant', on_delete=models.CASCADE, null=True, blank=True,
        related_name='stock_alerts', help_text='Empty = any configuration of this product.',
    )
    name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Back-in-stock request'

    def __str__(self):
        return f"{self.phone} — {self.product}"


class CartSnapshot(models.Model):
    """The logged-in customer's current cart, used for one reminder if they don't order."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart_snapshot')
    items = models.JSONField(default=list, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)
    reminded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Saved cart'

    def __str__(self):
        return f"{self.user} — {len(self.items)} item(s)"


class TradeInRequest(models.Model):
    """'Sell or exchange your old laptop' form."""
    STATUS_CHOICES = [
        ('new', 'New'),
        ('contacted', 'Contacted'),
        ('inspected', 'Inspected'),
        ('bought', 'Bought / exchanged'),
        ('closed', 'Closed'),
    ]
    CONDITION_CHOICES = [
        ('excellent', 'Excellent — like new'),
        ('good', 'Good — minor scratches'),
        ('fair', 'Fair — visible wear or small issues'),
        ('faulty', 'Not working / needs repair'),
    ]
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    city = models.CharField(max_length=100, blank=True)
    brand = models.CharField(max_length=50)
    model_name = models.CharField('Model', max_length=150, blank=True)
    processor = models.CharField(max_length=100, blank=True)
    ram = models.CharField(max_length=30, blank=True)
    storage = models.CharField(max_length=50, blank=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    has_charger = models.BooleanField(default=True)
    wants_exchange = models.BooleanField(default=False, help_text='Wants to exchange for a Yuva laptop.')
    notes = models.TextField(blank=True)
    photo_1 = models.ImageField(upload_to='trade_in/', blank=True)
    photo_2 = models.ImageField(upload_to='trade_in/', blank=True)
    photo_3 = models.ImageField(upload_to='trade_in/', blank=True)
    estimate_low = models.PositiveIntegerField(default=0)
    estimate_high = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Sell / exchange request'

    def __str__(self):
        return f"{self.name} — {self.brand} {self.model_name}".strip()


class CustomerPurchase(models.Model):
    """A past (mostly in-store) sale, imported from the sales register."""
    name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=10, db_index=True, help_text='10-digit mobile number.')
    sale_date = models.DateField(db_index=True)
    store = models.CharField(max_length=80, blank=True)
    model_name = models.CharField('Laptop / model', max_length=200, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    source_ref = models.CharField(
        max_length=40, help_text='Sheet + row number it came from, so re-importing updates instead of duplicating.'
    )
    marketing_opt_out = models.BooleanField(
        'Opted out of offers', default=False, help_text='Never include in offer broadcasts.'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sale_date']
        verbose_name = 'Past customer purchase'
        constraints = [models.UniqueConstraint(fields=['source_ref'], name='unique_purchase_source_ref')]

    def __str__(self):
        return f"{self.name or self.phone} — {self.sale_date:%d %b %Y}"
