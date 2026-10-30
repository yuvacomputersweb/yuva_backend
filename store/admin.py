"""
store/admin.py — Yuva Computers
Jazzmin-compatible admin with Excel Import / Export.

Requirements:
    pip install openpyxl
"""
from __future__ import annotations

from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import path
from django.utils.html import format_html

from .models import (
    WarrantyPlan,
    Brand, Category, UsageTag, Product,
    ProductVariant, ProductImage, Review, SiteConfig, Coupon,
)
from .utils.excel_utils import export_to_excel, import_from_excel


# ──────────────────────────── Excel mixin ────────────────────────────────────

class ExcelImportExportMixin:
    """
    Adds 'Export Excel' and 'Import Excel' buttons to any ModelAdmin.
    Works with default Django admin + Jazzmin theme.
    No third-party button library required.
    """

    change_list_template = "admin/store/change_list_with_excel.html"

    def get_urls(self):
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        custom = [
            path(
                "export-excel/",
                self.admin_site.admin_view(self.export_excel_view),
                name="%s_%s_export_excel" % info,
            ),
            path(
                "import-excel/",
                self.admin_site.admin_view(self.import_excel_view),
                name="%s_%s_import_excel" % info,
            ),
        ]
        return custom + urls

    # ── Export ────────────────────────────────────────────────────────────────
    def export_excel_view(self, request):
        data = export_to_excel(
            categories=Category.objects.all(),
            brands=Brand.objects.all(),
            usage_tags=UsageTag.objects.all(),
            products=Product.objects.select_related("category", "brand")
                                    .prefetch_related("usage_tags").all(),
            variants=ProductVariant.objects.select_related("product").all(),
            reviews=Review.objects.select_related("product").all(),
            coupons=Coupon.objects.all(),
            site_configs=SiteConfig.objects.all(),
        )
        response = HttpResponse(
            data,
            content_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
        )
        response["Content-Disposition"] = (
            'attachment; filename="yuva_store_data.xlsx"'
        )
        return response

    # ── Import ────────────────────────────────────────────────────────────────
    def import_excel_view(self, request):
        if request.method == "POST":
            xl_file = request.FILES.get("excel_file")
            if not xl_file:
                self.message_user(
                    request, "No file selected. Please choose an Excel file.",
                    level=messages.ERROR
                )
                return redirect(request.path)

            try:
                result = import_from_excel(xl_file)
            except Exception as e:
                self.message_user(
                    request, f"Import failed — {e}",
                    level=messages.ERROR
                )
                return redirect(request.path)

            # Show per-error warnings
            for err in result.errors:
                self.message_user(request, err, level=messages.WARNING)

            # Show overall summary
            self.message_user(
                request,
                f"Import complete — {result.summary()}",
                level=messages.SUCCESS,
            )
            return redirect("..")  # back to changelist

        ctx = self.admin_site.each_context(request)
        ctx.update({
            "title": "Import Products from Excel",
            "opts": self.model._meta,
        })
        return render(request, "admin/store/import_excel.html", ctx)


# ──────────────────────────── Inlines ────────────────────────────────────────

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ["image", "image_preview", "is_primary", "order"]
    readonly_fields = ["image_preview"]

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:60px;height:auto;border-radius:6px;" />',
                obj.image.url,
            )
        return "No Image"
    image_preview.short_description = "Preview"


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ["processor", "ram", "storage", "stock", "price_override"]


# ──────────────────────────── Model admins ────────────────────────────────────

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_featured")
    prepopulated_fields = {"slug": ("name",)}
    list_editable = ("is_featured",)


@admin.register(UsageTag)
class UsageTagAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Standalone admin for bulk variant management."""
    list_display = (
        "product", "processor", "ram", "storage",
        "stock", "price_override", "final_price"
    )
    list_filter = ("product", "processor", "ram", "storage")
    search_fields = ("product__sku", "product__title", "processor", "ram", "storage")
    list_editable = ("stock", "price_override")
    ordering = ("product", "processor", "ram", "storage")

    def final_price(self, obj):
        return f"₹{obj.product.price + obj.price_override:,.2f}"
    final_price.short_description = "Final Price"


@admin.register(Product)
class ProductAdmin(ExcelImportExportMixin, admin.ModelAdmin):
    list_display = (
        "sku", "title", "brand", "category", "condition",
        "price", "stock_mode", "stock", "warranty", "is_new_arrival", "is_best_seller",
        "is_trending", "is_best_deal", "is_active",
    )
    list_editable = (
        "stock", "is_new_arrival", "is_best_seller",
        "is_trending", "is_best_deal", "is_active",
    )
    list_filter = ("category", "brand", "condition", "is_active")
    search_fields = ("title", "sku", "processor")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("usage_tags",)
    inlines = [ProductImageInline, ProductVariantInline]

    _plan_cache: dict = {}

    def changelist_view(self, request, extra_context=None):
        self._plan_cache = {}  # fresh per page, so plan edits show straight away
        return super().changelist_view(request, extra_context)

    @admin.display(description="Warranty")
    def warranty(self, obj):
        from .warranty import plan_for_product
        plan = plan_for_product(obj, self._plan_cache)
        if not plan:
            return "—"
        return plan.name if obj.warranty_plan_id else f"{plan.name} (auto)"

    fieldsets = (
        ("Core Info", {
            "fields": (
                "title", "slug", "sku", "category",
                "brand", "condition", "usage_tags", "is_active",
            )
        }),
        ("Pricing", {
            "fields": ("price", "original_price")
        }),
        ("Warranty", {
            "fields": ("warranty_plan",),
            "description": "Leave empty and the right plan is picked automatically (shown in the product list).",
        }),
        ("Stock", {
            "fields": ("stock_mode", "stock"),
            "description": "Windows laptops: keep one count for the model — every RAM/SSD option sells from it, "
                           "and the configuration rows' own stock is ignored. MacBooks: choose 'Separate stock per "
                           "configuration' and set stock on each configuration row below.",
        }),
        ("Specifications", {
            "fields": (
                "processor", "ram", "storage", "display",
                "graphics", "operating_system", "battery",
                "weight", "ports", "wifi", "bluetooth",
            )
        }),
        ("Content", {
            "fields": ("description", "highlights")
        }),
        ("Video of this unit", {
            "fields": ("video_url", "video"),
            "description": "A short video of the actual laptop builds trust. Paste a YouTube link, or upload an MP4.",
        }),
        ("Refurbishment & Warranty", {
            "fields": (
                "refurbishment_summary", "refurbishment_points",
                "warranty_summary", "warranty_details",
            )
        }),
        ("Homepage Toggles", {
            "fields": (
                "is_new_arrival", "is_best_seller",
                "is_trending", "is_best_deal",
            )
        }),
        ("Trust Badges (Per Product)", {
            "fields": ("service_centers", "warranty_period", "return_policy")
        }),
    )


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("user_name", "product", "rating", "is_featured", "image_preview")
    list_editable = ("is_featured",)
    list_filter = ("rating", "is_featured")
    readonly_fields = ("image_preview",)

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width:80px;height:auto;" />',
                obj.image.url,
            )
        return "—"


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    list_display = ("shipping_fee", "whatsapp_number", "alert_whatsapp_numbers")
    fieldsets = (
        ("Shipping & payment", {"fields": ("shipping_fee", "free_shipping_threshold", "cod_surcharge_percentage", "tax_percentage")}),
        ("WhatsApp", {"fields": ("whatsapp_number", "alert_whatsapp_numbers", "low_stock_threshold")}),
        ("Warranty terms for all plans (plans: Store → Warranty plans)", {"fields": (
            "shipping_assurance", "warranty_exclusions", "warranty_void_conditions",
            "warranty_terms", "warranty_claim_steps",
        )}),
        ("Refurbishment & service (same on every product)", {"fields": (
            "refurbishment_summary", "refurbishment_points", "service_summary",
        )}),
        ("Product pages", {"fields": ("in_the_box",)}),
    )

    def has_add_permission(self, request):
        return SiteConfig.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ("code", "description", "discount_type", "value", "min_order_value", "is_public", "first_order_only", "active", "valid_to", "uses_count")
    list_editable = ("is_public", "active")
    list_filter = ("active", "is_public", "first_order_only", "discount_type")
    search_fields = ("code",)
    readonly_fields = ("uses_count",)


@admin.register(WarrantyPlan)
class WarrantyPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "badge", "testing_days", "parts_months", "free_service", "service_months", "battery_hours")
    list_display_links = ("name",)
    ordering = ("sort_order",)
    readonly_fields = ("code",)
    fieldsets = (
        (None, {"fields": ("name", "code", "badge", "summary", "sort_order")}),
        ("Cover", {"fields": ("testing_days", "parts_months", "free_service", "service_months", "battery_hours")}),
        ("Shown to customers", {"fields": ("points",)}),
    )

    def has_delete_permission(self, request, obj=None):
        return False  # the automatic rules look plans up by code
