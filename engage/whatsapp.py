"""
WhatsApp messages that aren't tied to one order: back-in-stock, cart
reminders and alerts to the shop owner. Every send is logged in
WhatsAppMessage and never raises.

Template variables (create each template in WATI, see WHATSAPP_TEMPLATES.md):

  back_in_stock    {{product_name}} {{product_link}}
  cart_reminder    {{name}} {{product_name}} {{cart_link}}
  low_stock_alert  {{product_name}} {{stock_left}}
  daily_summary    {{date}} {{new_orders}} {{revenue}} {{to_ship}} {{pending_returns}}
  new_lead         {{lead_type}} {{customer_name}} {{customer_phone}} {{details}}
  return_update    {{name}} {{order_number}} {{status}} {{note}}
"""
import logging

from django.conf import settings

from orders.notifications import send_wati_template

logger = logging.getLogger("orders.services")

_TEMPLATES = {
    'back_in_stock': ('WA_TEMPLATE_BACK_IN_STOCK', 'back_in_stock'),
    'cart_reminder': ('WA_TEMPLATE_CART_REMINDER', 'cart_reminder'),
    'low_stock': ('WA_TEMPLATE_LOW_STOCK', 'low_stock_alert'),
    'daily_summary': ('WA_TEMPLATE_DAILY_SUMMARY', 'daily_summary'),
    'new_lead': ('WA_TEMPLATE_NEW_LEAD', 'new_lead'),
    'return_update': ('WA_TEMPLATE_RETURN_UPDATE', 'return_update'),
}


def site_url(path: str = '') -> str:
    return getattr(settings, 'SITE_URL', 'https://www.yuvacomputers.in').rstrip('/') + path


def send(kind: str, phone: str, params: dict) -> bool:
    from .models import WhatsAppMessage

    setting, default = _TEMPLATES[kind]
    template = getattr(settings, setting, default)
    if not template:
        return False
    try:
        # WhatsApp rejects empty variables.
        params = {k: (str(v).strip() or '—') for k, v in params.items()}
        ok, response = send_wati_template(phone, template, params, f"{kind}")
    except Exception as exc:  # noqa: BLE001
        ok, response = False, str(exc)
    try:
        WhatsAppMessage.objects.create(
            kind=kind, phone=phone or '', template=template, params=params,
            success=ok, response=response[:2000],
        )
    except Exception:  # noqa: BLE001
        logger.exception('[WhatsApp] could not log message')
    (logger.info if ok else logger.error)(f"[WhatsApp] {kind} → {phone}: {'sent' if ok else 'FAILED'} {response[:200]}")
    return ok


def owner_numbers() -> list[str]:
    """Numbers that receive shop alerts (Admin → Site Configuration)."""
    from store.models import SiteConfig

    config = SiteConfig.objects.first()
    raw = getattr(config, 'alert_whatsapp_numbers', '') or getattr(config, 'whatsapp_number', '') or '919709888456'
    return [n.strip() for n in raw.replace(';', ',').split(',') if n.strip()]


def alert_owner(kind: str, params: dict) -> None:
    for number in owner_numbers():
        send(kind, number, params)
