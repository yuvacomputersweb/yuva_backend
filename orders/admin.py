# orders/admin.py
from django.contrib import admin
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import format_html
from .models import Order, OrderItem, ReturnRequest, ExchangeCode
import csv


def export_to_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=orders.csv'
    writer = csv.writer(response)
    writer.writerow([
        'Order ID', 'Name', 'Email', 'Phone',
        'Product Total', 'COD Charge Paid Online', 'Due on Delivery',
        'Payment Method', 'Payment Status', 'Order Status',
        'City', 'State', 'Delhivery Waybill', 'WhatsApp Sent', 'Date',
    ])
    for o in queryset:
        writer.writerow([
            o.id, f"{o.first_name} {o.last_name}", o.email, o.phone,
            o.total_amount,
            o.advance_amount if o.is_partial_cod else '—',
            o.collectible_cod_amount if o.is_partial_cod else '—',
            o.payment_method, o.payment_status, o.order_status,
            o.city, o.state,
            o.delhivery_waybill or '—',
            'Yes' if o.whatsapp_sent else 'No',
            timezone.localtime(o.created_at).strftime("%d-%m-%Y %H:%M"),
        ])
    return response

export_to_csv.short_description = "Export selected to CSV"


class OrderItemInline(admin.TabularInline):
    model         = OrderItem
    extra         = 0
    readonly_fields = ['product_name', 'variant_label', 'price', 'quantity', 'image_preview']

    def image_preview(self, obj):
        if obj.image_url:
            return format_html('<img src="{}" style="width:50px;height:auto;" />', obj.image_url)
        return "—"
    image_preview.short_description = "Image"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'full_name', 'email', 'total_amount',
        'payment_method', 'payment_status', 'order_status',
        'cod_charge_display', 'cod_due_display',
        'delhivery_waybill_display', 'whatsapp_sent', 'created_at',
    ]
    list_editable  = ['order_status', 'payment_status']
    list_filter    = [
        'payment_status', 'order_status', 'payment_method',
        'is_partial_cod', 'whatsapp_sent', 'created_at',
    ]
    search_fields  = [
        'id', 'first_name', 'last_name', 'email', 'phone',
        'razorpay_order_id', 'delhivery_waybill',
    ]
    readonly_fields = [
        'created_at', 'updated_at',
        'razorpay_order_id', 'razorpay_payment_id',
        'delhivery_waybill', 'whatsapp_sent',
        # COD fields are system-computed at checkout — never edited in admin
        'advance_amount', 'collectible_cod_amount', 'is_partial_cod',
    ]
    actions       = [export_to_csv]
    inlines       = [OrderItemInline]
    list_per_page = 25

    fieldsets = (
        ('Customer', {
            'fields': (('first_name', 'last_name'), 'email', 'phone'),
        }),
        ('Shipping Address', {
            'fields': (
                'shipping_address', 'apartment', 'landmark',
                'city', 'state', 'zip_code', 'country',
            ),
        }),
        ('Product Financials', {
            'description': 'These values reflect the product cost only. COD service charge is shown separately below.',
            'fields': (
                'subtotal', 'discount_amount', 'shipping_fee',
                'tax_amount', 'total_amount',
                'coupon_code', 'exchange_code_used',
            ),
        }),
        ('COD Service Charge Breakdown', {
            'description': (
                'advance_amount = COD upfront charge (2% of subtotal) + 18% GST on that charge. '
                'This amount was paid ONLINE via Razorpay. It is NON-REFUNDABLE. '
                'collectible_cod_amount = full product price paid by customer to the delivery agent.'
            ),
            'fields': ('is_partial_cod', 'advance_amount', 'collectible_cod_amount'),
        }),
        ('Payment & Order Status', {
            'fields': (
                'payment_method', 'payment_status', 'delivered_at',
                'order_status', 'razorpay_order_id', 'razorpay_payment_id',
            ),
        }),
        ('Policy', {
            'fields': ('accepted_return_policy',),
        }),
        ('Tracking & Logistics', {
            'fields': (
                'tracking_link', 'tracking_note',
                'delhivery_waybill', 'whatsapp_sent',
            ),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"
    full_name.short_description = "Customer"

    def cod_charge_display(self, obj):
        if obj.is_partial_cod:
            return format_html(
                '<span style="color:#2563eb;font-weight:600;" title="COD charge + GST paid online">₹{}</span>',
                obj.advance_amount
            )
        return "—"
    cod_charge_display.short_description = "COD Charge Paid"

    def cod_due_display(self, obj):
        if obj.is_partial_cod:
            return format_html(
                '<span style="color:#d97706;font-weight:600;" title="Product price due at delivery">₹{}</span>',
                obj.collectible_cod_amount
            )
        return "—"
    cod_due_display.short_description = "Due at Delivery"

    def delhivery_waybill_display(self, obj):
        if obj.delhivery_waybill:
            return format_html(
                '<span style="color:#16a34a;font-weight:600;">{}</span>',
                obj.delhivery_waybill,
            )
        return format_html('<span style="color:#9ca3af;">—</span>')
    delhivery_waybill_display.short_description = "Waybill"

    def save_model(self, request, obj, form, change):
        if change and 'order_status' in form.changed_data and obj.order_status == 'Delivered':
            if not obj.delivered_at:
                obj.delivered_at = timezone.now()

        super().save_model(request, obj, form, change)

        # Trigger logistics for COD when admin confirms or ships
        cod_trigger_statuses = ('Confirmed', 'Shipped')
        status_changed = change and 'order_status' in form.changed_data
        is_cod         = obj.payment_method == 'COD'

        if status_changed and is_cod and obj.order_status in cod_trigger_statuses:
            try:
                from .services import process_order_logistics_and_notification
                process_order_logistics_and_notification(obj)
                obj.refresh_from_db()

                if obj.delhivery_waybill:
                    self.message_user(
                        request,
                        f"✅ Delhivery shipment created — Waybill: {obj.delhivery_waybill}",
                        level='SUCCESS',
                    )
                else:
                    self.message_user(
                        request,
                        "⚠️ Delhivery shipment could not be created. Check server logs.",
                        level='WARNING',
                    )

                if obj.whatsapp_sent:
                    self.message_user(
                        request,
                        f"✅ WhatsApp message sent to {obj.phone}",
                        level='SUCCESS',
                    )
                else:
                    self.message_user(
                        request,
                        "⚠️ WhatsApp message could not be sent. Check server logs.",
                        level='WARNING',
                    )

            except Exception as exc:
                import logging as _logging
                _logging.getLogger(__name__).error(
                    f"[Admin] Logistics trigger failed for Order #{obj.id}: {exc}",
                    exc_info=True,
                )
                self.message_user(
                    request,
                    f"❌ Logistics error for Order #{obj.id}: {exc}",
                    level='ERROR',
                )


def approve_and_generate_code(modeladmin, request, queryset):
    for req in queryset.filter(status='Pending'):
        req.status = 'Approved'
        req.save()
approve_and_generate_code.short_description = "Approve selected requests"


def reject_request(modeladmin, request, queryset):
    queryset.filter(status='Pending').update(
        status='Rejected',
        admin_notes="Your return request has been reviewed and rejected. Contact support if you have questions."
    )
reject_request.short_description = "Reject selected requests"


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display    = ['id', 'get_order_id', 'get_customer', 'request_type', 'status', 'has_video', 'created_at']
    list_filter     = ['status', 'request_type']
    search_fields   = ['order__id', 'order__user__email']
    readonly_fields = ['order', 'user', 'created_at', 'updated_at', 'exchange_code']
    actions         = [approve_and_generate_code, reject_request]
    list_per_page   = 25

    def get_order_id(self, obj):  return f"#{obj.order.id}"
    get_order_id.short_description = "Order"

    def get_customer(self, obj):  return obj.user.email
    get_customer.short_description = "Customer"

    def has_video(self, obj):     return bool(obj.defect_video_url)
    has_video.boolean = True
    has_video.short_description = "Video?"


@admin.register(ExchangeCode)
class ExchangeCodeAdmin(admin.ModelAdmin):
    list_display    = ['code', 'get_order', 'original_order_value', 'is_used', 'expires_at', 'created_at']
    list_filter     = ['is_used']
    search_fields   = ['code', 'order__id']
    readonly_fields = ['code', 'created_at', 'used_at']
    list_per_page   = 25

    def get_order(self, obj): return f"Order #{obj.order.id}"
    get_order.short_description = "Order"