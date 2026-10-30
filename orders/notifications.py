# orders/notifications.py
"""
Customer WhatsApp notifications for every stage of an order (via WATI).

Each event maps to a WATI template whose name comes from settings, so a
template can be renamed — or an event switched off by setting its name to
"" — without code changes. Every send is recorded in OrderNotification,
which also stops the same event being sent twice for one order.

Templates are sent with *named* parameters. Create each template in WATI
with exactly these variables (see WHATSAPP_TEMPLATES.md):

  order_placed      {{name}} {{order_number}} {{total_price}}
  payment_received  {{name}} {{order_number}} {{amount}}
  order_shipped     {{name}} {{order_number}} {{awb}} {{tracking_link}}
  out_for_delivery  {{name}} {{order_number}} {{amount_due}}
  order_delivered   {{name}} {{order_number}}
  order_cancelled   {{name}} {{order_number}}
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger("orders.services")

EVENTS = {
    "order_placed": "Order placed",
    "payment_received": "Payment received",
    "order_shipped": "Shipped",
    "out_for_delivery": "Out for delivery",
    "order_delivered": "Delivered",
    "order_cancelled": "Cancelled",
}

# settings name -> default WATI template name
_TEMPLATE_SETTINGS = {
    "order_placed": ("WA_TEMPLATE_NAME", "order_placed"),
    "payment_received": ("WA_TEMPLATE_PAYMENT_RECEIVED", "payment_received"),
    "order_shipped": ("WA_TEMPLATE_ORDER_SHIPPED", "order_shipped"),
    "out_for_delivery": ("WA_TEMPLATE_OUT_FOR_DELIVERY", "out_for_delivery"),
    "order_delivered": ("WA_TEMPLATE_ORDER_DELIVERED", "order_delivered"),
    "order_cancelled": ("WA_TEMPLATE_ORDER_CANCELLED", "order_cancelled"),
}


def template_for(event: str) -> str:
    setting, default = _TEMPLATE_SETTINGS[event]
    return getattr(settings, setting, default)


def format_wati_phone(phone: str) -> str:
    """Convert to WATI format: 91XXXXXXXXXX (no + sign, no spaces)."""
    phone = (phone or "").strip().replace(" ", "").replace("-", "")
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("91") and len(phone) == 12:
        return phone
    if phone.startswith("0") and len(phone) == 11:
        return f"91{phone[1:]}"
    if len(phone) == 10:
        return f"91{phone}"
    logger.warning(f"[PhoneFormat] Unexpected format: '{phone}' — prefixing 91")
    return f"91{phone}"


def tracking_url(order) -> str:
    if order.tracking_link:
        return order.tracking_link
    if order.delhivery_waybill:
        return f"https://www.delhivery.com/track-v2/package/{order.delhivery_waybill}"
    site = getattr(settings, "SITE_URL", "https://www.yuvacomputers.in").rstrip("/")
    return f"{site}/track-order?order={order.id}"


def _rupees(value) -> str:
    return f"Rs. {float(value or 0):,.2f}"


def build_params(order, event: str) -> dict:
    params = {
        "name": (order.first_name or "Customer").strip(),
        "order_number": str(order.id),
    }
    if event == "order_placed":
        params["total_price"] = _rupees(order.total_amount)
    elif event == "payment_received":
        paid = order.advance_amount if order.payment_status == "Deposit Paid" else order.total_amount
        params["amount"] = _rupees(paid)
    elif event == "order_shipped":
        params["awb"] = order.delhivery_waybill or "—"
        params["tracking_link"] = tracking_url(order)
    elif event == "out_for_delivery":
        due = order.collectible_cod_amount if order.payment_method == "COD" else 0
        params["amount_due"] = _rupees(due) if due else "Nothing — already paid"
    return params


def send_wati_template(phone: str, template_name: str, params: dict, broadcast_name: str) -> tuple[bool, str]:
    """Send one WATI template message. Returns (ok, response text)."""
    access_token = getattr(settings, "WA_ACCESS_TOKEN", "")
    base_api_url = getattr(settings, "WA_API_URL", "https://live-mt-server.wati.io/308273")
    if not access_token:
        return False, "WA_ACCESS_TOKEN not configured"
    if not phone:
        return False, "Order has no phone number"

    url = f"{base_api_url.rstrip('/')}/api/v1/sendTemplateMessage"
    try:
        response = requests.post(
            url,
            params={"whatsappNumber": format_wati_phone(phone)},
            json={
                "template_name": template_name,
                "broadcast_name": broadcast_name,
                "parameters": [{"name": k, "value": str(v)} for k, v in params.items()],
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            timeout=25,
        )
    except requests.RequestException as exc:
        return False, f"Request failed: {exc}"

    text = response.text[:1000]
    if response.status_code not in (200, 201):
        return False, f"HTTP {response.status_code}: {text}"
    try:
        result = response.json()
    except ValueError:
        return False, f"Non-JSON response: {text}"
    ok = result.get("result") is True or result.get("result") == "success"
    return ok, text


def notify(order, event: str, force: bool = False) -> bool:
    """
    Send the WhatsApp message for `event` once per order. Never raises —
    a failed message must not break checkout, payment or admin saves.
    """
    from .models import OrderNotification

    try:
        template = template_for(event)
        if not template:
            logger.info(f"[WhatsApp] Order #{order.id} {event}: disabled in settings")
            return False
        if not force and OrderNotification.objects.filter(order=order, event=event, success=True).exists():
            logger.info(f"[WhatsApp] Order #{order.id} {event}: already sent")
            return False

        params = build_params(order, event)
        ok, response = send_wati_template(order.phone, template, params, f"Order_{order.id}_{event}")
        OrderNotification.objects.create(
            order=order, event=event, template=template, phone=order.phone or "",
            success=ok, response=response,
        )
        log = logger.info if ok else logger.error
        log(f"[WhatsApp] Order #{order.id} {event} via '{template}': {'sent' if ok else 'FAILED'} — {response[:300]}")

        if ok and event == "order_placed" and not order.whatsapp_sent:
            type(order).objects.filter(pk=order.pk).update(whatsapp_sent=True)
            order.whatsapp_sent = True
        return ok
    except Exception as exc:  # noqa: BLE001 — notifications must never break the caller
        logger.error(f"[WhatsApp] Order #{order.id} {event}: {exc}", exc_info=True)
        return False
