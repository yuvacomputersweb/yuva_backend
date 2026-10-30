"""
Confirm an order once Razorpay has the money — used by the webhook, the
admin (payment marked paid by hand) and the check_pending_payments command,
so a payment is never lost when the customer's browser closes before the
normal verify step.
"""
import logging

from django.db import transaction

from orders.models import Order

logger = logging.getLogger(__name__)

PAID_STATUSES = ('Paid', 'Deposit Paid')


def trigger_logistics(order) -> None:
    """Delhivery shipment + 'order placed' WhatsApp. Never raises."""
    try:
        from orders.services import process_order_logistics_and_notification
        process_order_logistics_and_notification(order)
    except Exception as exc:  # noqa: BLE001 — third-party failures must not block payment
        logger.error(f"[Payments] Logistics trigger failed for Order #{order.id}: {exc}", exc_info=True)


def take_order_stock(order) -> None:
    for item in order.items.select_related('variant__product').all():
        if item.variant:
            item.variant.take_stock(item.quantity)


def confirm_paid_order(order, rzp_payment_id: str = '') -> bool:
    """
    Mark the order paid (online) or deposit paid (COD), take stock, then
    create the shipment and send WhatsApp. Does nothing if already paid.
    Returns True when it confirmed the order.
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.payment_status in PAID_STATUSES:
            return False
        take_order_stock(order)
        if rzp_payment_id:
            order.razorpay_payment_id = rzp_payment_id
        order.order_status = 'Processing'
        order.payment_status = 'Deposit Paid' if order.is_partial_cod else 'Paid'
        order.save()
    trigger_logistics(order)
    logger.info(f"[Payments] Order #{order.id} confirmed ({order.payment_status}) payment={rzp_payment_id or '-'}")
    return True
