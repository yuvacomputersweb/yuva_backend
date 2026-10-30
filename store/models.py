#store/models-yuva
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


class WarrantyPlan(models.Model):
    """
    A warranty package. Each product gets one automatically (see
    store/warranty.py) unless a plan is picked on the product.
    """
    code = models.SlugField(unique=True, help_text="Used by the automatic rules: standard, basic, graphics, apple, monitor.")
    name = models.CharField(max_length=80, help_text='e.g. "1-Year Warranty"')
    badge = models.CharField(max_length=60, help_text="Short line for product cards and trust badges.")
    summary = models.CharField(max_length=200)
    testing_days = models.PositiveIntegerField(default=15, help_text="Testing warranty from the date of purchase. 0 = none.")
    parts_months = models.PositiveIntegerField(
        default=0, help_text="RAM & hard disk replacement + motherboard repair, in months. 0 = not included."
    )
    free_service = models.BooleanField(default=True, help_text="Free service at Yuva Service Lab (spare parts chargeable).")
    service_months = models.PositiveIntegerField(
        default=0, help_text="How long free service lasts, in months. 0 = no time limit."
    )
    battery_hours = models.PositiveSmallIntegerField(
        default=1, help_text="Minimum battery backup guaranteed, in hours. 0 = not applicable."
    )
    points = models.TextField(help_text="What is covered, one point per line. Shown on the product's Warranty tab.")
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'id']

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
    video_url = models.URLField(
        max_length=500, blank=True,
        help_text="YouTube / YouTube Shorts link of the actual unit (recommended — loads fastest)."
    )
    video = models.FileField(
        upload_to='product_videos/', blank=True,
        help_text="Or upload a short MP4 (under 20 MB). Used only when there is no video link."
    )

    # ── Stock ──
    STOCK_MODE_CHOICES = [
        ('model', 'One stock for the model — RAM/SSD upgraded to order'),
        ('variant', 'Separate stock per configuration (e.g. MacBooks)'),
    ]
    stock_mode = models.CharField(
        max_length=10, choices=STOCK_MODE_CHOICES, default='model',
        help_text="Windows laptops: one count for the model, any RAM/SSD option can be sold from it. "
                  "MacBooks can't be upgraded, so each configuration has its own count."
    )
    stock = models.PositiveIntegerField(
        default=0, help_text="Units of this model on hand. Used when stock mode is 'One stock for the model'."
    )

    warranty_plan = models.ForeignKey(
        WarrantyPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name='products',
        help_text="Leave empty to choose automatically: Apple → iStore plan; dedicated graphics → 6-month service; "
                  "monitors → no warranty; under ₹15,000 → 15-day testing; others → 1-year warranty."
    )

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

    # ── Stock helpers: the right counter depends on the product's stock mode ──

    @property
    def shares_model_stock(self) -> bool:
        return self.product.stock_mode == 'model'

    @property
    def available(self) -> int:
        """Units that can be sold in this configuration."""
        return self.product.stock if self.shares_model_stock else self.stock

    def _locked_stock_owner(self):
        """The live, row-locked object holding this configuration's count.
        Re-read so two lines of the same model in one order can't overwrite
        each other. Call inside a transaction."""
        if self.shares_model_stock:
            return Product.objects.select_for_update().get(pk=self.product_id)
        return ProductVariant.objects.select_for_update().get(pk=self.pk)

    def take_stock(self, quantity: int) -> bool:
        """Remove sold units. Saves with save() so stock alerts run. False if not enough."""
        from django.db import transaction
        with transaction.atomic():
            owner = self._locked_stock_owner()
            if owner.stock < quantity:
                return False
            owner.stock -= quantity
            owner.save(update_fields=['stock'])
        return True

    def return_stock(self, quantity: int) -> None:
        """Put units back (cancellation)."""
        from django.db import transaction
        with transaction.atomic():
            owner = self._locked_stock_owner()
            owner.stock += quantity
            owner.save(update_fields=['stock'])

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
    alert_whatsapp_numbers = models.CharField(
        max_length=200, default='919709888456', blank=True,
        help_text="Who gets shop alerts (new leads, low stock, daily summary). Comma-separated, with country code."
    )
    low_stock_threshold = models.PositiveIntegerField(
        default=1, help_text="Send a low-stock alert when a configuration drops to this many units."
    )
    # ── Warranty terms shared by every plan (plans themselves: Warranty plans) ──
    shipping_assurance = models.TextField(
        default=("Damaged in transit? It's on us. Record a clear, uncut video while opening the sealed "
                 "package — we need it to approve a transit-damage claim."),
        help_text="Shown on every product."
    )
    warranty_exclusions = models.TextField(
        default=(
            "Burn and physical damage: cracks, dents, broken body or hinges\n"
            "Keyboard, speakers and screen\n"
            "Liquid or water damage of any kind\n"
            "Battery, beyond the minimum backup guaranteed for the product\n"
            "Spare parts not listed in the product's warranty"
        ),
        blank=True, help_text="Not covered by any plan. One point per line. Shown on the warranty policy page."
    )
    warranty_void_conditions = models.TextField(
        default=(
            "Warranty sticker or seal broken, removed or tampered with\n"
            "Device opened or repaired outside Yuva Service Lab\n"
            "Serial number removed or not matching our records\n"
            "Original invoice not produced at the time of claim"
        ),
        blank=True, help_text="Warranty is void if… One point per line. Shown on the warranty policy page."
    )
    warranty_terms = models.TextField(
        default=(
            "Once goods are sold they cannot be taken back as a return. Exchange or replacement within the testing period only if the device is undamaged and in the same condition as delivered.\n"
            "No free part replacement other than what the product's warranty lists. Other parts are chargeable.\n"
            "Repairs at Yuva Service Lab carry a 15-day warranty on the same repair, from the date of delivery.\n"
            "Transit-damage claims need an unboxing video recorded while opening the sealed package.\n"
            "Data backup is the customer's responsibility.\n"
            "Yuva Computers' decision on warranty eligibility is final."
        ),
        blank=True, help_text="Terms & conditions. One point per line. Shown on the warranty policy page."
    )
    warranty_claim_steps = models.TextField(
        default=(
            "WhatsApp our service team on 9347145456 with your invoice or order number and a short video of the problem\n"
            "Our technician checks it, usually the same day\n"
            "Bring it to any Yuva store, or ship it back with Delhivery\n"
            "We repair or replace it as per your warranty and return it to you"
        ),
        blank=True, help_text="How to claim. One step per line."
    )
    refurbishment_summary = models.CharField(max_length=120, default="50-point quality check")
    refurbishment_points = models.TextField(
        default=(
            "Every component inspected individually, not in batches\n"
            "Faulty parts replaced in our in-house refurbishment lab\n"
            "Display checked for dead pixels, spots and backlight bleed\n"
            "Battery health tested and backup verified\n"
            "Keyboard, touchpad, ports, speakers, webcam and Wi-Fi tested\n"
            "Stress-tested for performance and heating\n"
            "Fresh, genuine OS installed with drivers and updates\n"
            "Deep-cleaned, sanitised and sealed with a Yuva warranty sticker"
        ),
        help_text="Shown on every product's Refurbishment tab. One point per line."
    )
    service_summary = models.CharField(max_length=80, default="Service at 17+ Yuva stores")

    in_the_box = models.TextField(
        default="Original charger\nFree laptop bag\nFree wireless mouse", blank=True,
        help_text="Shown as 'What's in the box' on laptop pages. One item per line."
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
    description = models.CharField(
        max_length=120, blank=True, help_text='Shown to customers, e.g. "Extra ₹500 off on your first order"'
    )
    is_public = models.BooleanField(default=False, help_text="Show this offer on product pages and at checkout.")
    first_order_only = models.BooleanField(default=False, help_text="Only for customers who haven't ordered before.")
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
