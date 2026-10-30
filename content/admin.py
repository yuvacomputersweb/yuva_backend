from django.contrib import admin
from django.utils.html import format_html
from .models import (
    HeroSlide, SiteStat, HomeReview, PartnerBrand, AboutContent,
    CompanyContent, CompanyTimeline, CompanyInvestor,
    CompanyCertification, CompanyPartner,
    BulkOrderContent, BulkOrderBenefit, BulkScalePoint, BulkInventoryItem,
    StoreLocation, StoresPageContent,
    ContactPageContent, ContactDepartment,Blog
)


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ['order', 'image_preview', 'is_active']
    list_editable = ['order', 'is_active']
    list_display_links = ['image_preview']

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="height:60px;border-radius:6px;" />', obj.image.url)
        return "—"
    image_preview.short_description = "Preview"


@admin.register(SiteStat)
class SiteStatAdmin(admin.ModelAdmin):
    list_display = ['value', 'label', 'order']
    list_editable = ['order']


@admin.register(HomeReview)
class HomeReviewAdmin(admin.ModelAdmin):
    list_display = ['name', 'rating', 'is_active', 'order']
    list_editable = ['is_active', 'order']


@admin.register(PartnerBrand)
class PartnerBrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'order', 'is_active']
    list_editable = ['order', 'is_active']


@admin.register(AboutContent)
class AboutContentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return AboutContent.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CompanyContent)
class CompanyContentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return CompanyContent.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CompanyTimeline)
class CompanyTimelineAdmin(admin.ModelAdmin):
    list_display = ['year', 'title', 'order']
    list_editable = ['order']


@admin.register(CompanyInvestor)
class CompanyInvestorAdmin(admin.ModelAdmin):
    list_display = ['name', 'type', 'order', 'is_active']
    list_editable = ['order', 'is_active']


@admin.register(CompanyCertification)
class CompanyCertificationAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'is_active']
    list_editable = ['order', 'is_active']


@admin.register(CompanyPartner)
class CompanyPartnerAdmin(admin.ModelAdmin):
    list_display = ['name', 'order', 'is_active']
    list_editable = ['order', 'is_active']


@admin.register(BulkOrderContent)
class BulkOrderContentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return BulkOrderContent.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BulkOrderBenefit)
class BulkOrderBenefitAdmin(admin.ModelAdmin):
    list_display = ['title', 'icon', 'order']
    list_editable = ['order']


@admin.register(BulkScalePoint)
class BulkScalePointAdmin(admin.ModelAdmin):
    list_display = ['text', 'order', 'is_active']
    list_editable = ['order', 'is_active']


@admin.register(BulkInventoryItem)
class BulkInventoryItemAdmin(admin.ModelAdmin):
    list_display = ['device_type', 'units_available', 'order']
    list_editable = ['order']


@admin.register(StoreLocation)
class StoreLocationAdmin(admin.ModelAdmin):
    list_display = ['name', 'state', 'phone', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['state', 'is_active']
    search_fields = ['name', 'phone']


@admin.register(StoresPageContent)
class StoresPageContentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return StoresPageContent.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContactPageContent)
class ContactPageContentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return ContactPageContent.objects.count() == 0

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ContactDepartment)
class ContactDepartmentAdmin(admin.ModelAdmin):
    list_display = ['label', 'number', 'icon', 'order', 'is_active']
    list_editable = ['order', 'is_active']

@admin.register(Blog)
class BlogAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'is_published', 'created_at', 'cover_preview']
    list_editable = ['is_published']
    list_display_links = ['title']
    prepopulated_fields = {'slug': ('title',)}
    readonly_fields = ['created_at', 'updated_at', 'cover_preview']
    search_fields = ['title', 'slug']
    list_filter = ['is_published']

    fieldsets = (
        (None, {
            'fields': ('title', 'slug', 'is_published')
        }),
        ('Cover Image', {
            'fields': ('cover_image', 'cover_preview')
        }),
        ('Content', {
            'fields': ('excerpt', 'paragraphs'),
            'description': (
                'paragraphs: Enter a JSON list of strings. Example: '
                '["First paragraph text.", "Second paragraph text."]'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" style="height:80px;border-radius:6px;" />',
                obj.cover_image.url
            )
        return "—"
    cover_preview.short_description = "Preview"
