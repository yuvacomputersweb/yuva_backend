from django.db import models


class HeroSlide(models.Model):
    image = models.ImageField(upload_to='content/hero/')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Hero Slide {self.order}"


class SiteStat(models.Model):
    label = models.CharField(max_length=100)
    value = models.CharField(max_length=50)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.value} — {self.label}"


class HomeReview(models.Model):
    name = models.CharField(max_length=100)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)], default=5)
    text = models.TextField()
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.name} ({self.rating}★)"


class PartnerBrand(models.Model):
    """Brands shown in the scrolling partners section on HomePage."""
    name = models.CharField(max_length=100, help_text="e.g. DELL, HP, LENOVO")
    color = models.CharField(
        max_length=20, blank=True, default='',
        help_text="Hex color e.g. #254fa0 (optional)"
    )
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class AboutContent(models.Model):
    """Singleton"""
    heading = models.CharField(max_length=255, default="Crafting Excellence Since 2009")
    vision_title = models.CharField(max_length=200, default="Our Vision")
    vision_text = models.TextField(
        default="To make high-end computing accessible to everyone without sacrificing the planet's resources."
    )
    mission_title = models.CharField(max_length=200, default="Our Mission")
    mission_text = models.TextField(
        default="Setting the gold standard in refurbishment through rigorous 50-step audits and industry-leading warranty support."
    )
    about_image_1 = models.ImageField(upload_to='content/about/', null=True, blank=True)
    about_image_2 = models.ImageField(upload_to='content/about/', null=True, blank=True)
    image_2_title = models.CharField(max_length=100, default="Quality Control")
    image_2_subtitle = models.CharField(max_length=100, default="We Made it Safe Work")

    class Meta:
        verbose_name = "About Content"
        verbose_name_plural = "About Content"

    def __str__(self):
        return "About Content"


# ── COMPANY PAGE ──────────────────────────────────────────────────────────────

class CompanyContent(models.Model):
    """Singleton"""
    hero_image = models.ImageField(upload_to='content/company/', null=True, blank=True)
    hero_title = models.CharField(max_length=255, default="Democratizing Technology Since 2009.")
    hero_subtitle = models.CharField(max_length=255, default="Yuva Computers", blank=True)

    story_heading = models.CharField(max_length=255, default="Our Journey Through Precision.")
    story_text = models.TextField(
        default="We started with a simple belief: high-end technology shouldn't be a luxury. It should be a standard."
    )

    vision_text = models.TextField(
        default="To eliminate digital obsolescence by creating a circular economy where technology is curated, not discarded."
    )
    mission_text = models.TextField(
        default="Providing every professional with the tools they deserve through meticulous engineering and uncompromising quality standards."
    )

    # Fueling the Future section
    fueling_heading = models.CharField(max_length=255, default="Fueling the Future.")
    fueling_subtext = models.CharField(
        max_length=255, default="Backed by leaders in sustainable tech and venture capital."
    )

    # Integrity section
    integrity_heading = models.CharField(max_length=255, default="Integrity in Every Interaction.")
    integrity_text = models.TextField(
        default="We partner with global leaders in electronics recycling and hardware certification."
    )

    # Partners section
    partners_label = models.CharField(max_length=100, default="Our Partners")

    cta_heading = models.CharField(max_length=255, default="Experience it before you buy.")
    cta_text = models.TextField(
        default="Visit our premium experience centers to test drive our curated selection of precision computing instruments."
    )

    class Meta:
        verbose_name = "Company Page Content"
        verbose_name_plural = "Company Page Content"

    def __str__(self):
        return "Company Page Content"


class CompanyTimeline(models.Model):
    year = models.CharField(max_length=10)
    title = models.CharField(max_length=100)
    description = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.year} — {self.title}"


class CompanyInvestor(models.Model):
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=200, help_text="e.g. Early Stage Growth")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class CompanyCertification(models.Model):
    name = models.CharField(max_length=200, help_text="e.g. Certified E-Recycler")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


class CompanyPartner(models.Model):
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name


# ── BULK ORDERS PAGE ──────────────────────────────────────────────────────────

class BulkOrderContent(models.Model):
    """Singleton"""
    hero_image = models.ImageField(upload_to='content/bulk/', null=True, blank=True)
    hero_title = models.CharField(max_length=255, default="Equip Your Workspace.")
    hero_title_highlight = models.CharField(max_length=100, default="Smartly.")
    hero_subtitle = models.TextField(
        default="Transform your team's productivity with certified refurbished devices."
    )

    section_heading = models.CharField(
        max_length=255, default="Scale Your Infrastructure Without Compromise."
    )
    section_text = models.TextField(
        default="Our enterprise team will build a custom quote within 2 working days."
    )

    inventory_image = models.ImageField(upload_to='content/bulk/', null=True, blank=True)
    inventory_heading = models.CharField(max_length=255, default="Ready for Deployment.")
    inventory_text = models.TextField(
        default="We maintain ready stock so your new hires start on day one."
    )

    class Meta:
        verbose_name = "Bulk Orders Page Content"
        verbose_name_plural = "Bulk Orders Page Content"

    def __str__(self):
        return "Bulk Orders Page Content"


class BulkOrderBenefit(models.Model):
    ICON_CHOICES = [
        ('truck', 'Truck / Delivery'),
        ('settings', 'Settings / Config'),
        ('shield', 'Shield / Security'),
        ('check', 'Check / Verified'),
        ('star', 'Star'),
        ('zap', 'Zap / Fast'),
    ]
    title = models.CharField(max_length=200)
    description = models.TextField()
    icon = models.CharField(max_length=50, choices=ICON_CHOICES, default='check')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title


class BulkScalePoint(models.Model):
    """Bullet points under 'Scale Your Infrastructure' section."""
    text = models.CharField(max_length=255, help_text="e.g. Priority PAN-India Logistics")
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.text


class BulkInventoryItem(models.Model):
    device_type = models.CharField(max_length=100)
    units_available = models.CharField(max_length=50, help_text="e.g. 500+ Units")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.device_type} — {self.units_available}"


# ── STORES PAGE ───────────────────────────────────────────────────────────────

class StoreLocation(models.Model):
    STATE_CHOICES = [
        ('Telangana', 'Telangana'),
        ('Andhra Pradesh', 'Andhra Pradesh'),
    ]
    name = models.CharField(max_length=200, help_text="e.g. Yuva Computers - Dilsukhnagar")
    state = models.CharField(max_length=100, choices=STATE_CHOICES, default='Telangana')
    phone = models.CharField(max_length=20)
    maps_url = models.URLField(blank=True, help_text="Google Maps URL")
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['state', 'order']

    def __str__(self):
        return self.name


class StoresPageContent(models.Model):
    """Singleton — page heading and note text."""
    page_heading = models.CharField(
        max_length=255,
        default="Ready for Discovery? Explore Our Stores Today!"
    )
    page_subtext = models.TextField(
        default="Yuva Computers Physical Stores. Now proudly serving in 2 Major States."
    )
    note_text = models.TextField(
        default="Please contact respective branches for the pricelist. To find our exact locations, search Google for 'Yuva Computers [Branch Area]' (e.g., 'Yuva Computers Warangal')."
    )

    class Meta:
        verbose_name = "Stores Page Content"
        verbose_name_plural = "Stores Page Content"

    def __str__(self):
        return "Stores Page Content"


# ── CONTACT PAGE ──────────────────────────────────────────────────────────────

class ContactPageContent(models.Model):
    """Singleton"""
    hero_heading = models.CharField(max_length=255, default="We're Here to Help.")
    hero_subtext = models.TextField(
        default="Whether you're troubleshooting a workstation or planning a bulk deployment, our experts are ready."
    )

    # Department numbers (stored as JSON-like repeating model entries)
    whatsapp_number = models.CharField(max_length=20, default="919709888456")
    email_support = models.EmailField(default="info@yuvacomputers.in")
    email_response_time = models.CharField(max_length=100, default="Response within 2 working days.")

    # Grievance
    grievance_officer_name = models.CharField(max_length=100, default="Rajender Kumar")
    grievance_officer_email = models.EmailField(default="grievance@yuvacomputers.com")

    # Main branch
    branch_name = models.CharField(max_length=200, default="Dilshuknagar Main Branch")
    branch_address = models.TextField(
        default="Metro Pillar No. 1519, Sai Towers, 204, 2nd Floor, above Tipsy Topsy Bakery, Dilsukhnagar, Hyderabad, TS 500060"
    )
    branch_hours = models.CharField(max_length=100, default="Daily: 10:00 AM - 08:30 PM")
    branch_maps_url = models.URLField(
        default="https://maps.app.goo.gl/ChIJ3UKGZBCayzsRR8Nw_iIbU8g"
    )
    branch_maps_embed = models.TextField(
        blank=True,
        help_text="Full Google Maps embed src URL"
    )

    class Meta:
        verbose_name = "Contact Page Content"
        verbose_name_plural = "Contact Page Content"

    def __str__(self):
        return "Contact Page Content"


class ContactDepartment(models.Model):
    ICON_CHOICES = [
        ('wrench', 'Wrench / Service'),
        ('shopping-cart', 'Cart / Sales'),
        ('message-square', 'Message / Complaints'),
        ('phone', 'Phone'),
        ('mail', 'Mail'),
    ]
    label = models.CharField(max_length=100, help_text="e.g. For Service")
    number = models.CharField(max_length=30, help_text="e.g. +91 9347145456")
    icon = models.CharField(max_length=30, choices=ICON_CHOICES, default='phone')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.label} — {self.number}"
    
# ── BLOG / MINI CMS ───────────────────────────────────────────────────────────

class Blog(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True, blank=True, max_length=280)
    cover_image = models.ImageField(upload_to='content/blogs/')
    excerpt = models.TextField(
        help_text="Short preview shown on cards. Auto-generated from paragraphs if left blank.",
        blank=True
    )
    paragraphs = models.JSONField(
        default=list,
        help_text='Store as a JSON array of strings: ["Para 1...", "Para 2..."]'
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Auto-generate slug
        if not self.slug:
            from django.utils.text import slugify
            base = slugify(self.title)
            slug = base
            n = 1
            while Blog.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        # Auto-generate excerpt from first paragraph if not set
        if not self.excerpt and self.paragraphs:
            first = self.paragraphs[0] if isinstance(self.paragraphs, list) else ""
            self.excerpt = first[:200] + ("..." if len(first) > 200 else "")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
