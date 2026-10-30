from django.contrib import admin
from django.utils.html import format_html

from .models import CartSnapshot, StockAlert, TradeInRequest, WhatsAppMessage


@admin.register(TradeInRequest)
class TradeInRequestAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'name', 'phone_link', 'brand', 'model_name', 'condition', 'estimate', 'wants_exchange', 'status')
    list_filter = ('status', 'condition', 'brand', 'wants_exchange')
    list_editable = ('status',)
    search_fields = ('name', 'phone', 'model_name', 'city')
    readonly_fields = ('created_at', 'photos', 'estimate_low', 'estimate_high')
    fieldsets = (
        ('Customer', {'fields': ('name', 'phone', 'city', 'created_at')}),
        ('Laptop', {'fields': ('brand', 'model_name', 'processor', 'ram', 'storage', 'condition', 'has_charger', 'wants_exchange', 'notes')}),
        ('Photos', {'fields': ('photos', 'photo_1', 'photo_2', 'photo_3')}),
        ('Our side', {'fields': ('estimate_low', 'estimate_high', 'status', 'admin_notes')}),
    )

    @admin.display(description='Phone')
    def phone_link(self, obj):
        return format_html('<a href="https://wa.me/91{}" target="_blank">{}</a>', obj.phone[-10:], obj.phone)

    @admin.display(description='Website estimate')
    def estimate(self, obj):
        return f"₹{obj.estimate_low:,} – ₹{obj.estimate_high:,}" if obj.estimate_high else '—'

    @admin.display(description='Preview')
    def photos(self, obj):
        imgs = [p for p in (obj.photo_1, obj.photo_2, obj.photo_3) if p]
        if not imgs:
            return 'No photos'
        return format_html(''.join(
            f'<a href="{p.url}" target="_blank"><img src="{p.url}" style="height:120px;margin-right:8px;border-radius:8px"></a>'
            for p in imgs
        ))


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'phone', 'name', 'product', 'variant', 'notified_at')
    list_filter = ('notified_at',)
    search_fields = ('phone', 'product__title')
    autocomplete_fields = ()
    raw_id_fields = ('product', 'variant')


@admin.register(CartSnapshot)
class CartSnapshotAdmin(admin.ModelAdmin):
    list_display = ('user', 'item_titles', 'total', 'updated_at', 'reminded_at')
    readonly_fields = ('user', 'items', 'total', 'updated_at', 'reminded_at')
    search_fields = ('user__email',)

    @admin.display(description='Items')
    def item_titles(self, obj):
        return ', '.join(i.get('title', '') for i in obj.items)[:120]

    def has_add_permission(self, request):
        return False


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'kind', 'phone', 'template', 'success')
    list_filter = ('kind', 'success')
    search_fields = ('phone',)
    readonly_fields = [f.name for f in WhatsAppMessage._meta.fields]

    def has_add_permission(self, request):
        return False
