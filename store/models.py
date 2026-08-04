#store/models
from django.db import models
from django.utils.text import slugify
from django.utils import timezone


class Brand(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    image = models.ImageField(upload_to='categories/', null=True, blank=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class UsageTag(models.Model):
    """Gaming, Coding, School, Trading, Video/Graphics, Accounting"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    icon = models.CharField(
        max_length=50, blank=True,
        help_text="Lucide icon name e.g. 'monitor', 'code', 'gamepad'"
    )

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    CONDITION_CHOICES = [
        ('like_new', 'Like New'),
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('value', 'Value'),
    ]

    # Core
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True)
    sku = models.CharField(max_length=50, unique=True, help_text="e.g. YC-LT-001")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='excellent')
    usage_tags = models.ManyToManyField(UsageTag, blank=True, related_name='products')
    service_centers = models.CharField(max_length=100, default="350+ Service Centers")
    warranty_period = models.CharField(max_length=100, default="1 Year Warranty")
    return_policy = models.CharField(max_length=100, default="14 Days Return")

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="MRP / original price for showing discount"
    )

    # Specs
    processor = models.CharField(max_length=255, blank=True)
    ram = models.CharField(max_length=50, blank=True, help_text="e.g. 8GB DDR4")
    storage = models.CharField(max_length=100, blank=True, help_text="e.g. 256GB SSD")
    display = models.CharField(max_length=100, blank=True, help_text="e.g. 14inch FHD")
    graphics = models.CharField(max_length=100, blank=True, help_text="e.g. NVIDIA GTX 1650")
    operating_system = models.CharField(max_length=100, blank=True, default='Windows 11 Pro')
    battery = models.CharField(max_length=100, blank=True)
    weight = models.CharField(max_length=50, blank=True)
    ports = models.CharField(max_length=255, blank=True)
    wifi = models.CharField(max_length=100, blank=True, default='Wi-Fi 6')
    bluetooth = models.CharField(max_length=50, blank=True, default='Bluetooth 5.0')

    # Content
    description = models.TextField(blank=True)
    highlights = models.TextField(
        blank=True,
        help_text="One highlight per line. e.g: Fast SSD\\nLong battery life"
    )
    refurbishment_summary = models.CharField(
        max_length=255, blank=True,
        default='40+ Quality Checks Passed'
    )
    refurbishment_points = models.TextField(
        blank=True,
        help_text="One point per line e.g: Battery Health: 92%\\nNo scratches"
    )
    warranty_summary = models.CharField(
        max_length=255, blank=True, default='6 Months Warranty'
    )
    warranty_details = models.TextField(
        blank=True,
        help_text="One detail per line e.g: Covers hardware defects\\n15-day return"
    )

    # Homepage toggles
    is_new_arrival = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)
    is_best_deal = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.sku} — {self.title}"

    class Meta:
        ordering = ['-created_at']


class ProductVariant(models.Model):
    """Processor + RAM + Storage combinations with stock and optional price override"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    # ADDED: processor field — blank/default so existing rows without processor still work
    processor = models.CharField(
        max_length=255, blank=True, default='',
        help_text="e.g. Intel Core i5-10th Gen. Leave blank if not applicable."
    )
    ram = models.CharField(max_length=50, help_text="e.g. 8GB")
    storage = models.CharField(max_length=100, help_text="e.g. 256GB SSD")
    stock = models.PositiveIntegerField(default=0)
    price_override = models.DecimalField(
        max_digits=10, decimal_places=2, default=0.00,
        help_text="Extra amount added to base price for this variant"
    )

    def __str__(self):
        parts = [self.product.sku]
        if self.processor:
            parts.append(self.processor)
        parts.extend([self.ram, self.storage])
        return " | ".join(parts)

    class Meta:
        # UPDATED: processor is now part of the unique combination
        unique_together = ('product', 'processor', 'ram', 'storage')


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/')
    is_primary = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'id']

    def __str__(self):
        return f"Image for {self.product.sku}"


class Review(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user_name = models.CharField(max_length=100)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField()
    image = models.ImageField(upload_to='reviews/', null=True, blank=True)
    location = models.CharField(max_length=100, default='India')
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    variant_info = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.user_name} — {self.product.title} ({self.rating}★)"


class SiteConfig(models.Model):
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    free_shipping_threshold = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cod_surcharge_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=2.00)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    whatsapp_number = models.CharField(
        max_length=20, default='919709888456',
        help_text="Include country code, no + sign. e.g. 919709888456"
    )

    class Meta:
        verbose_name = "Site Configuration"
        verbose_name_plural = "Site Configuration"

    def __str__(self):
        return "Site Configuration"


class Coupon(models.Model):
    DISCOUNT_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    ]
    code = models.CharField(max_length=50, unique=True)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_CHOICES)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valid_from = models.DateTimeField()
    valid_to = models.DateTimeField()
    active = models.BooleanField(default=True)
    usage_limit = models.IntegerField(default=100)
    uses_count = models.IntegerField(default=0)

    def is_valid(self):
        now = timezone.now()
        return (
            self.active and
            self.valid_from <= now <= self.valid_to and
            self.uses_count < self.usage_limit
        )

    def __str__(self):
        return f"{self.code} ({self.discount_type} — {self.value})"