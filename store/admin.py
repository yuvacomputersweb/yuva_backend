#store/admin
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Brand, Category, UsageTag, Product,
    ProductVariant, ProductImage, Review, SiteConfig, Coupon
)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_featured')
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ('is_featured',)


@admin.register(UsageTag)
class UsageTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'icon')
    prepopulated_fields = {'slug': ('name',)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ['image', 'image_preview', 'is_primary', 'order']
    readonly_fields = ['image_preview']

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:60px;height:auto;border-radius:6px;" />',
                obj.image.url
            )
        return "No Image"
    image_preview.short_description = "Preview"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    # UPDATED: added processor field
    fields = ['processor', 'ram', 'storage', 'stock', 'price_override']


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Standalone admin for bulk variant management"""
    list_display = ('product', 'processor', 'ram', 'storage', 'stock', 'price_override', 'final_price')
    list_filter = ('product', 'processor', 'ram', 'storage')
    search_fields = ('product__sku', 'product__title', 'processor', 'ram', 'storage')
    list_editable = ('stock', 'price_override')
    ordering = ('product', 'processor', 'ram', 'storage')

    def final_price(self, obj):
        return f"₹{obj.product.price + obj.price_override:,.2f}"
    final_price.short_description = "Final Price"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'sku', 'title', 'brand', 'category', 'condition',
        'price', 'is_new_arrival', 'is_best_seller',
        'is_trending', 'is_best_deal', 'is_active'
    )
    list_editable = (
        'is_new_arrival', 'is_best_seller',
        'is_trending', 'is_best_deal', 'is_active'
    )
    list_filter = ('category', 'brand', 'condition', 'is_active')
    search_fields = ('title', 'sku', 'processor')
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ('usage_tags',)
    inlines = [ProductImageInline, ProductVariantInline]

    fieldsets = (
        ('Core Info', {
            'fields': (
                'title', 'slug', 'sku', 'category',
                'brand', 'condition', 'usage_tags', 'is_active'
            )
        }),
        ('Pricing', {
            'fields': ('price', 'original_price')
        }),
        ('Specifications', {
            'fields': (
                'processor', 'ram', 'storage', 'display',
                'graphics', 'operating_system', 'battery',
                'weight', 'ports', 'wifi', 'bluetooth'
            )
        }),
        ('Content', {
            'fields': ('description', 'highlights')
        }),
        ('Refurbishment & Warranty', {
            'fields': (
                'refurbishment_summary', 'refurbishment_points',
                'warranty_summary', 'warranty_details'
            )
        }),
        ('Homepage Toggles', {
            'fields': (
                'is_new_arrival', 'is_best_seller',
                'is_trending', 'is_best_deal'
            )
        }),
        ('Trust Badges (Per Product)', {
            'fields': ('service_centers', 'warranty_period', 'return_policy')
        }),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user_name', 'product', 'rating', 'is_featured', 'image_preview')
    list_editable = ('is_featured',)
    list_filter = ('rating', 'is_featured')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:80px;height:auto;" />',
                obj.image.url
            )
        return "—"


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ('shipping_fee', 'whatsapp_number')

    def has_add_permission(self, request):
        return SiteConfig.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'value', 'active', 'valid_to', 'uses_count')
    list_filter = ('active', 'discount_type')
    search_fields = ('code',)
    readonly_fields = ('uses_count',)