"""Automatic WhatsApp messages driven by stock, return and trade-in changes."""
from django.db import transaction
from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from orders.models import ReturnRequest
from store.models import ProductVariant, SiteConfig

from .models import StockAlert, TradeInRequest
from .whatsapp import alert_owner, send, site_url


# ── Stock: back-in-stock messages and low-stock alerts ───────────────────────

@receiver(pre_save, sender=ProductVariant)
def _remember_stock(sender, instance, **kwargs):
    instance._previous_stock = (
        sender.objects.filter(pk=instance.pk).values_list('stock', flat=True).first() if instance.pk else None
    )


def notify_back_in_stock(variant):
    alerts = StockAlert.objects.filter(product=variant.product, notified_at__isnull=True).filter(
        Q(variant=variant) | Q(variant__isnull=True)
    )
    link = site_url(f'/product/{variant.product.slug}')
    for alert in alerts:
        send('back_in_stock', alert.phone, {'product_name': variant.product.title, 'product_link': link})
        alert.notified_at = timezone.now()
        alert.save(update_fields=['notified_at'])


@receiver(post_save, sender=ProductVariant)
def _stock_changed(sender, instance, created, **kwargs):
    old = getattr(instance, '_previous_stock', None)
    new = instance.stock

    if (old == 0 or (created and new > 0)) and new > 0:
        transaction.on_commit(lambda: notify_back_in_stock(instance))

    config = SiteConfig.objects.first()
    threshold = getattr(config, 'low_stock_threshold', 1)
    if old is not None and new < old and new <= threshold:
        label = ' / '.join(x for x in [instance.processor, instance.ram, instance.storage] if x)
        params = {
            'product_name': f"{instance.product.title} ({label})" if label else instance.product.title,
            'stock_left': str(new),
        }
        transaction.on_commit(lambda: alert_owner('low_stock', params))


# ── Return / replacement requests ────────────────────────────────────────────

@receiver(pre_save, sender=ReturnRequest)
def _remember_return_status(sender, instance, **kwargs):
    # Keep the first value: approving a request re-saves it (to attach the
    # exchange code) before the outer save's post_save handlers run.
    if not hasattr(instance, '_previous_status'):
        instance._previous_status = (
            sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first() if instance.pk else None
        )


RETURN_STATUS_TEXT = {
    'Pending': 'received — our team will review it within 1 working day',
    'Approved': 'approved',
    'Rejected': 'not approved',
}


@receiver(post_save, sender=ReturnRequest)
def _return_changed(sender, instance, created, **kwargs):
    order = instance.order
    name = (order.first_name or 'Customer').strip()

    if created:
        transaction.on_commit(lambda: alert_owner('new_lead', {
            'lead_type': f"{instance.get_request_type_display()} request",
            'customer_name': f"{order.first_name} {order.last_name}".strip() or name,
            'customer_phone': order.phone,
            'details': f"Order #{order.id}: {instance.defect_description[:300]}",
        }))

    if not hasattr(instance, '_previous_status'):
        return  # already handled by a nested save
    old = instance._previous_status
    del instance._previous_status
    if created or (old and old != instance.status):
        note = instance.admin_notes or 'Reply to this message if you have any questions.'
        if instance.status == 'Approved' and instance.exchange_code_id:
            code = instance.exchange_code
            note = f"{note} Your exchange code: {code.code} (valid till {code.expires_at:%d %b %Y})." if code.expires_at \
                else f"{note} Your exchange code: {code.code}."
        params = {
            'name': name,
            'order_number': str(order.id),
            'status': RETURN_STATUS_TEXT.get(instance.status, instance.status.lower()),
            'note': note[:400],
        }
        transaction.on_commit(lambda: send('return_update', order.phone, params))


# ── Sell / exchange old laptop ───────────────────────────────────────────────

@receiver(post_save, sender=TradeInRequest)
def _trade_in_created(sender, instance, created, **kwargs):
    if not created:
        return
    details = ', '.join(x for x in [
        f"{instance.brand} {instance.model_name}".strip(), instance.processor, instance.ram, instance.storage,
        instance.get_condition_display(), instance.city,
        f"estimate Rs. {instance.estimate_low:,}-{instance.estimate_high:,}" if instance.estimate_high else '',
        'wants exchange' if instance.wants_exchange else '',
    ] if x)
    transaction.on_commit(lambda: alert_owner('new_lead', {
        'lead_type': 'Sell / exchange laptop',
        'customer_name': instance.name,
        'customer_phone': instance.phone,
        'details': details[:500],
    }))
