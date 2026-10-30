import csv
from datetime import date, timedelta

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html

from .customer_import import import_sales_register
from .models import CartSnapshot, CustomerPurchase, StockAlert, TradeInRequest, WhatsAppMessage
from .views import _add_months, store_policy


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


# ── Past customers ───────────────────────────────────────────────────────────

def _months_ago(months: int) -> date:
    return _add_months(timezone.localdate(), -months)


class WarrantyFilter(admin.SimpleListFilter):
    title = 'warranty'
    parameter_name = 'warranty'

    def lookups(self, request, model_admin):
        return [
            ('testing', 'In 15-day testing warranty'),
            ('active', 'Parts warranty active'),
            ('expiring', 'Expiring in next 30 days'),
            ('expired', 'Expired'),
        ]

    def queryset(self, request, qs):
        days, months, _ = store_policy()
        today = timezone.localdate()
        start = _add_months(today, -months)  # bought after this → still covered
        if self.value() == 'testing':
            return qs.filter(sale_date__gte=today - timedelta(days=days))
        if self.value() == 'active':
            return qs.filter(sale_date__gt=start)
        if self.value() == 'expiring':
            return qs.filter(sale_date__gt=start, sale_date__lte=start + timedelta(days=30))
        if self.value() == 'expired':
            return qs.filter(sale_date__lte=start)
        return qs


class PurchaseAgeFilter(admin.SimpleListFilter):
    title = 'bought'
    parameter_name = 'bought'

    def lookups(self, request, model_admin):
        return [
            ('15d', 'Last 15 days (ask for a Google review)'),
            ('1y', 'Under 1 year (service check-up)'),
            ('1-3y', '1–3 years ago (RAM/SSD/battery upgrade)'),
            ('3y', '3+ years ago (exchange offer)'),
        ]

    def queryset(self, request, qs):
        today = timezone.localdate()
        if self.value() == '15d':
            return qs.filter(sale_date__gte=today - timedelta(days=15))
        if self.value() == '1y':
            return qs.filter(sale_date__gt=_months_ago(12))
        if self.value() == '1-3y':
            return qs.filter(sale_date__lte=_months_ago(12), sale_date__gt=_months_ago(36))
        if self.value() == '3y':
            return qs.filter(sale_date__lte=_months_ago(36))
        return qs


class ImportForm(forms.Form):
    file = forms.FileField(help_text='The sales register Excel (.xlsx). Re-uploading the same rows updates them.')
    store = forms.CharField(initial='Dilsukhnagar HQ', help_text='Used when a row has no store.')


@admin.register(CustomerPurchase)
class CustomerPurchaseAdmin(admin.ModelAdmin):
    change_list_template = 'admin/engage/customerpurchase/change_list.html'
    list_display = ('sale_date', 'name', 'phone_link', 'model_name', 'store', 'amount', 'warranty', 'marketing_opt_out')
    list_filter = (WarrantyFilter, PurchaseAgeFilter, 'store', 'marketing_opt_out')
    list_editable = ('marketing_opt_out',)
    search_fields = ('name', 'phone', 'model_name')
    date_hierarchy = 'sale_date'
    readonly_fields = ('source_ref', 'created_at')
    actions = ['export_for_whatsapp']
    list_per_page = 50

    @admin.display(description='Phone')
    def phone_link(self, obj):
        return format_html('<a href="https://wa.me/91{}" target="_blank">{}</a>', obj.phone, obj.phone)

    @admin.display(description='Warranty')
    def warranty(self, obj):
        days, months, _ = store_policy()
        today = timezone.localdate()
        end = _add_months(obj.sale_date, months)
        if obj.sale_date >= today - timedelta(days=days):
            return format_html('<b style="color:#4c8a1f">Testing period</b>')
        if end >= today:
            return format_html('<span style="color:#4c8a1f">Till {}</span>', end.strftime('%d %b %Y'))
        return format_html('<span style="color:#999">Expired</span>')

    @admin.action(description='Export selected for WhatsApp / Meta ads (CSV, one row per phone, skips opt-outs)')
    def export_for_whatsapp(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="yuva_customers.csv"'
        writer = csv.writer(response)
        writer.writerow(['Name', 'Phone', 'Last purchase', 'Model', 'Store'])
        seen = set()
        for p in queryset.filter(marketing_opt_out=False).order_by('phone', '-sale_date'):
            if p.phone in seen:
                continue
            seen.add(p.phone)
            writer.writerow([p.name, f'91{p.phone}', p.sale_date.isoformat(), p.model_name, p.store])
        return response

    def get_urls(self):
        return [
            path('import/', self.admin_site.admin_view(self.import_view), name='engage_customerpurchase_import'),
        ] + super().get_urls()

    def import_view(self, request):
        form = ImportForm(request.POST or None, request.FILES or None)
        if request.method == 'POST' and form.is_valid():
            try:
                stats = import_sales_register(form.cleaned_data['file'], default_store=form.cleaned_data['store'])
            except Exception as exc:  # noqa: BLE001 — show any file problem to the admin
                messages.error(request, f'Could not import: {exc}')
            else:
                messages.success(request, (
                    f"Imported/updated {stats['imported']} of {stats['rows']} rows. "
                    f"Skipped {stats['skipped_no_phone']} without a valid mobile and {stats['skipped_no_date']} without a date."
                ))
                return redirect('admin:engage_customerpurchase_changelist')
        context = {
            **self.admin_site.each_context(request),
            'title': 'Import past customers',
            'form': form,
            'opts': self.model._meta,
        }
        return render(request, 'admin/engage/customerpurchase/import.html', context)
