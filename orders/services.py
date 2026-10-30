# orders/services.py
"""
Logistics & Notification Service Layer
Yuva Computers — Delhivery One + WATI WhatsApp Gateway

Trigger rules:
  - Online orders:  payments/views.py  → after payment_status = 'Paid'
  - COD orders:     payments/views.py  → after payment_status = 'Deposit Paid'
                    orders/admin.py    → when admin sets status to 'Confirmed' or 'Shipped'

Delhivery COD amount:
  - For COD orders, cod_amount sent to Delhivery = collectible_cod_amount
    (i.e. the 98% the delivery agent collects — NOT the full total_amount)
  - This is correct because the customer already paid 2% online.
"""

import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _format_e164(phone: str) -> str:
    """
    Convert to WATI-compatible format: 91XXXXXXXXXX (no + sign, no spaces).
    """
    phone = phone.strip().replace(" ", "").replace("-", "")
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


# ─── MAIN ORCHESTRATOR ───────────────────────────────────────────────────────

def process_order_logistics_and_notification(order) -> None:
    """
    Central runner. Idempotent — safe to call multiple times.
    Checks delhivery_waybill and whatsapp_sent flags before firing.
    """
    logger.info(f"[Logistics] Order #{order.id} | method={order.payment_method} | status={order.payment_status}")

    # ── Delhivery shipment creation
    if not order.delhivery_waybill:
        try:
            waybill = create_delhivery_order(order)
            if waybill:
                order.delhivery_waybill = waybill
                order.save(update_fields=["delhivery_waybill"])
                logger.info(f"[Delhivery] Order #{order.id} → waybill: {waybill}")
            else:
                logger.warning(f"[Delhivery] Order #{order.id} → no waybill returned")
        except Exception as exc:
            logger.error(f"[Delhivery] Order #{order.id} failed: {exc}", exc_info=True)
    else:
        logger.info(f"[Delhivery] Order #{order.id} already has waybill '{order.delhivery_waybill}' — skipping")

    # ── WhatsApp notification
    if not order.whatsapp_sent:
        try:
            sent = send_whatsapp_order_placed_msg(order)
            if sent:
                order.whatsapp_sent = True
                order.save(update_fields=["whatsapp_sent"])
                logger.info(f"[WhatsApp] Order #{order.id} → message sent")
            else:
                logger.warning(f"[WhatsApp] Order #{order.id} → message NOT sent")
        except Exception as exc:
            logger.error(f"[WhatsApp] Order #{order.id} failed: {exc}", exc_info=True)
    else:
        logger.info(f"[WhatsApp] Order #{order.id} already notified — skipping")


# ─── DELHIVERY ───────────────────────────────────────────────────────────────

def create_delhivery_order(order) -> str | None:
    """
    Create a Delhivery shipment via the CMU endpoint.

    COD amount logic:
      - COD orders: send collectible_cod_amount (98% — what delivery agent collects)
        NOT total_amount (customer already paid 2% advance online)
      - Online orders: cod_amount = 0 (fully prepaid)

    For orders above ₹50,000: Delhivery will reject unless an E-Way bill is
    added manually in the Delhivery One dashboard after creation.
    """
    api_token  = getattr(settings, "DELHIVERY_API_TOKEN", "")
    api_url    = getattr(settings, "DELHIVERY_API_URL", "https://track.delhivery.com")
    pickup_loc = getattr(settings, "DELHIVERY_PICKUP_LOCATION", "")

    if not api_token:
        logger.error("[Delhivery] DELHIVERY_API_TOKEN not configured")
        return None
    if not pickup_loc:
        logger.error("[Delhivery] DELHIVERY_PICKUP_LOCATION not configured")
        return None

    total_qty    = sum(item.quantity for item in order.items.all())
    is_cod       = order.payment_method == "COD"
    payment_mode = "COD" if is_cod else "Pre-paid"

    # ── KEY FIX: use collectible_cod_amount for COD, not total_amount ─────────
    # collectible_cod_amount = total_amount - advance_amount (98%)
    # The delivery agent only collects the balance, not the full order value.
    if is_cod:
        cod_amount = float(order.collectible_cod_amount)
    else:
        cod_amount = 0

    shipment_data = {
        "shipments": [
            {
                "name":            f"{order.first_name} {order.last_name}".strip(),
                "add":             order.shipping_address,
                "pin":             order.zip_code,
                "city":            order.city,
                "state":           order.state,
                "country":         order.country or "India",
                "phone":           order.phone,
                "order":           str(order.id),
                "payment_mode":    payment_mode,
                "cod_amount":      cod_amount,           # ← 98% balance (correct)
                "total_amount":    float(order.total_amount),  # ← full product value
                "shipment_width":  10,
                "shipment_height": 10,
                "shipment_length": 15,
                "weight":          500 * total_qty,      # 500g/item — update per client
                "quantity":        total_qty,
                "seller_name":     "Yuva Computers",
                "seller_add":      "Hyderabad, Telangana",
                "seller_inv":      str(order.id),
                "return_pin":      "500001",
                "return_city":     "Hyderabad",
                "return_phone":    "9100000000",
                "return_name":     "Yuva Computers",
                "return_add":      "Yuva Computers, Hyderabad",
                "return_state":    "Telangana",
                "return_country":  "India",
            }
        ],
        "pickup_location": {"name": pickup_loc},
    }

    endpoint  = f"{api_url.rstrip('/')}/api/cmu/create.json"
    headers   = {"Authorization": f"Token {api_token}"}
    form_data = {"format": "json", "data": json.dumps(shipment_data)}

    logger.info(
        f"[Delhivery] POST {endpoint} | Order #{order.id} | "
        f"₹{order.total_amount} total | COD collectible: ₹{cod_amount} | {payment_mode}"
    )

    response = requests.post(endpoint, data=form_data, headers=headers, timeout=15)
    logger.info(f"[Delhivery] HTTP {response.status_code}: {response.text[:800]}")

    if response.status_code not in (200, 201):
        logger.error(f"[Delhivery] HTTP error {response.status_code}: {response.text[:500]}")
        return None

    try:
        result = response.json()
    except Exception:
        logger.error(f"[Delhivery] Non-JSON response: {response.text[:300]}")
        return None

    packages = result.get("packages", [])
    if packages:
        first      = packages[0]
        waybill    = first.get("waybill", "")
        pkg_status = first.get("status", "")

        if waybill and pkg_status == "Success":
            return waybill

        logger.error(
            f"[Delhivery] Package failed | status='{pkg_status}' | "
            f"waybill='{waybill}' | remarks='{first.get('remarks', [])}'"
        )
        return None

    logger.error(f"[Delhivery] No packages in response: {result}")
    return None


# ─── WHATSAPP (WATI) ─────────────────────────────────────────────────────────

def send_whatsapp_order_placed_msg(order) -> bool:
    """
    Send 'Order Placed' via WATI.
    whatsappNumber goes in the query string, not the JSON body.
    """
    access_token  = getattr(settings, "WA_ACCESS_TOKEN", "")
    template_name = getattr(settings, "WA_TEMPLATE_NAME", "order_placed")
    base_api_url  = getattr(settings, "WA_API_URL", "https://live-mt-server.wati.io/308273")

    if not access_token:
        logger.error("[WhatsApp] WA_ACCESS_TOKEN not configured")
        return False
    if not order.phone:
        logger.error(f"[WhatsApp] Order #{order.id} has no phone number")
        return False

    recipient_phone = _format_e164(order.phone)
    first_name      = (order.first_name or "Customer").strip()
    order_id        = str(order.id)
    total_amount    = f"Rs. {float(order.total_amount):,.2f}"

    url     = f"{base_api_url.rstrip('/')}/api/v1/sendTemplateMessage"
    params  = {"whatsappNumber": recipient_phone}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }
    payload = {
        "template_name":  template_name,
        "broadcast_name": f"Order_{order_id}",
        "parameters": [
            {"name": "name",         "value": first_name},
            {"name": "order_number", "value": order_id},
            {"name": "total_price",  "value": total_amount},
        ],
    }

    logger.info(f"[WhatsApp] → {recipient_phone} | Order #{order_id}")

    try:
        response = requests.post(url, params=params, json=payload, headers=headers, timeout=25)
        logger.info(f"[WhatsApp] HTTP {response.status_code}: {response.text}")

        if response.status_code not in (200, 201):
            logger.error(f"[WhatsApp] Failed HTTP {response.status_code}: {response.text[:500]}")
            return False

        result = response.json()
        if result.get("result") is True or result.get("result") == "success":
            return True

        logger.error(f"[WhatsApp] Unexpected response: {result}")
        return False

    except requests.exceptions.Timeout:
        logger.error(f"[WhatsApp] Order #{order.id} — request timed out")
        return False
    except Exception as exc:
        logger.error(f"[WhatsApp] Order #{order.id} — exception: {exc}", exc_info=True)
        return False
