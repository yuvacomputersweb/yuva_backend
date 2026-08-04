# orders/services.py
"""
Logistics & Notification Service Layer
Yuva Computers — Delhivery One + WATI WhatsApp Gateway

Trigger rules:
  - Online (Razorpay): called from payments/views.py after payment_status → 'Paid'
  - COD: called from orders/admin.py when admin sets status → 'Confirmed' or 'Shipped'

Safety: all external calls are wrapped so they NEVER block the core order flow.
"""

import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def _format_e164(phone: str) -> str:
    """
    Convert an Indian phone number to E.164 format WITHOUT the + sign.
    WATI requires: 91XXXXXXXXXX  (no + prefix, no spaces)

    Handles all common Indian formats:
      9876543210        → 919876543210
      09876543210       → 919876543210
      +919876543210     → 919876543210
      919876543210      → 919876543210  (already correct)
    """
    phone = phone.strip().replace(" ", "").replace("-", "")

    # Strip leading + if present
    if phone.startswith("+"):
        phone = phone[1:]

    # Already has 91 prefix and correct length
    if phone.startswith("91") and len(phone) == 12:
        return phone

    # Has leading 0 (STD format)
    if phone.startswith("0") and len(phone) == 11:
        return f"91{phone[1:]}"

    # Plain 10-digit number
    if len(phone) == 10:
        return f"91{phone}"

    # Unknown format — prefix 91 and hope for the best, log it
    logger.warning(f"[PhoneFormat] Unexpected phone format: '{phone}' — prefixing 91")
    return f"91{phone}"


# ─── MAIN ORCHESTRATOR ───────────────────────────────────────────────────────

def process_order_logistics_and_notification(order) -> None:
    """
    Central runner. Call this after an order is confirmed/paid.
    Idempotent: safe to call multiple times — checks flags before firing.

    Args:
        order: orders.models.Order instance (already saved to DB)
    """
    logger.info(f"[Logistics] Starting for Order #{order.id} | method={order.payment_method}")

    # ── Step 1: Delhivery shipment creation
    if not order.delhivery_waybill:
        try:
            waybill = create_delhivery_order(order)
            if waybill:
                order.delhivery_waybill = waybill
                order.save(update_fields=["delhivery_waybill"])
                logger.info(f"[Delhivery] Order #{order.id} → waybill saved: {waybill}")
            else:
                logger.warning(f"[Delhivery] Order #{order.id} → no waybill returned (check API response logs above)")
        except Exception as exc:
            # Log full traceback but do NOT re-raise — never block checkout
            logger.error(f"[Delhivery] Order #{order.id} failed: {exc}", exc_info=True)
    else:
        logger.info(f"[Delhivery] Order #{order.id} already has waybill '{order.delhivery_waybill}' — skipping")

    # ── Step 2: WhatsApp "Order Placed" notification
    if not order.whatsapp_sent:
        try:
            sent = send_whatsapp_order_placed_msg(order)
            if sent:
                order.whatsapp_sent = True
                order.save(update_fields=["whatsapp_sent"])
                logger.info(f"[WhatsApp] Order #{order.id} → message sent successfully")
            else:
                logger.warning(f"[WhatsApp] Order #{order.id} → message NOT sent (see error logs above)")
        except Exception as exc:
            logger.error(f"[WhatsApp] Order #{order.id} failed: {exc}", exc_info=True)
    else:
        logger.info(f"[WhatsApp] Order #{order.id} already notified — skipping")


# ─── DELHIVERY ───────────────────────────────────────────────────────────────

def create_delhivery_order(order) -> str | None:
    """
    Create a shipment on Delhivery One via the CMU creation endpoint.

    - Works for ALL order amounts including above ₹50,000.
      The client will manually add E-Way bill on Delhivery dashboard after creation.
    - Returns the per-shipment waybill string on success.
    - Never falls back to upload_wbn (batch ID) — that's not a trackable waybill.
    - Returns None on any failure so the orchestrator logs it cleanly.
    """
    api_token  = getattr(settings, "DELHIVERY_API_TOKEN", "")
    api_url    = getattr(settings, "DELHIVERY_API_URL", "https://track.delhivery.com")
    pickup_loc = getattr(settings, "DELHIVERY_PICKUP_LOCATION", "")

    if not api_token:
        logger.error("[Delhivery] DELHIVERY_API_TOKEN is not configured in settings/.env")
        return None
    if not pickup_loc:
        logger.error("[Delhivery] DELHIVERY_PICKUP_LOCATION is not configured in settings/.env")
        return None

    total_qty    = sum(item.quantity for item in order.items.all())
    is_cod       = order.payment_method == "COD"
    payment_mode = "COD" if is_cod else "Pre-paid"
    cod_amount   = float(order.total_amount) if is_cod else 0

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
                "cod_amount":      cod_amount,
                "total_amount":    float(order.total_amount),
                "shipment_width":  10,
                "shipment_height": 10,
                "shipment_length": 15,
                "weight":          500 * total_qty,    # 500g per item — update per client
                "quantity":        total_qty,
                "seller_name":     "Yuva Computers",
                "seller_add":      "Hyderabad, Telangana",
                "seller_inv":      str(order.id),
                "return_pin":      "500001",
                "return_city":     "Hyderabad",
                "return_phone":    "9100000000",        # update to store phone
                "return_name":     "Yuva Computers",
                "return_add":      "Yuva Computers, Hyderabad",
                "return_state":    "Telangana",
                "return_country":  "India",
            }
        ],
        "pickup_location": {
            "name": pickup_loc,
        },
    }

    endpoint  = f"{api_url.rstrip('/')}/api/cmu/create.json"
    headers   = {"Authorization": f"Token {api_token}"}
    form_data = {"format": "json", "data": json.dumps(shipment_data)}

    logger.info(f"[Delhivery] POST {endpoint} | Order #{order.id} | ₹{order.total_amount} | {payment_mode}")

    response = requests.post(endpoint, data=form_data, headers=headers, timeout=15)

    logger.info(f"[Delhivery] Response HTTP {response.status_code}: {response.text[:800]}")

    if response.status_code not in (200, 201):
        logger.error(f"[Delhivery] Order #{order.id} HTTP error {response.status_code}: {response.text[:500]}")
        return None

    try:
        result = response.json()
    except Exception:
        logger.error(f"[Delhivery] Order #{order.id} — response is not valid JSON: {response.text[:300]}")
        return None

    # ── Extract waybill from individual shipment package only ──────────────
    # NEVER use result.get("upload_wbn") — that is a batch-level upload ID,
    # not a trackable shipment waybill. Using it would store corrupted tracking data.
    packages = result.get("packages", [])
    if packages:
        first = packages[0]
        waybill = first.get("waybill", "")
        pkg_status = first.get("status", "")

        if waybill and pkg_status == "Success":
            return waybill

        # Shipment was received but individual package failed validation
        logger.error(
            f"[Delhivery] Order #{order.id} package not successful. "
            f"status='{pkg_status}' | waybill='{waybill}' | "
            f"error='{first.get('error', 'none')}' | "
            f"remarks='{first.get('remarks', 'none')}'"
        )
        return None

    # No packages array at all — log full response for debugging
    logger.error(
        f"[Delhivery] Order #{order.id} — no 'packages' key in response. "
        f"Full response: {result}"
    )
    return None


# ─── WHATSAPP (WATI GATEWAY) ─────────────────────────────────────────────────
def send_whatsapp_order_placed_msg(order) -> bool:
    """
    Send a transactional "Order Placed" message via the WATI multi-tenant gateway.
    Strictly mapped to the verified template tokens from the WATI dashboard.
    """
    access_token  = getattr(settings, "WA_ACCESS_TOKEN", "")
    template_name = getattr(settings, "WA_TEMPLATE_NAME", "order_placed")
    base_api_url  = getattr(settings, "WA_API_URL", "https://live-mt-server.wati.io/308273")

    if not access_token:
        logger.error("[WhatsApp] WA_ACCESS_TOKEN is not configured in settings/.env")
        return False

    if not order.phone:
        logger.error(f"[WhatsApp] Order #{order.id} has no phone number — cannot send message")
        return False

    recipient_phone = _format_e164(order.phone)
    first_name   = (order.first_name or "Customer").strip()
    order_id     = str(order.id)
    total_amount = f"Rs. {float(order.total_amount):,.2f}"

    url = f"{base_api_url.rstrip('/')}/api/v1/sendTemplateMessage"
    params = {"whatsappNumber": recipient_phone}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type":  "application/json",
        "Accept":        "application/json",
    }

    # ─── THE DEFINITIVE ACCURATE PAYLOAD ───
    # Using the exact keys found in image_3646c0.png and image_364983.png
    payload = {
        "template_name": template_name,
        "broadcast_name": f"Order_{order_id}",
        "channel_number": "919709888456",  # ◄ Real business number from dashboard header
        "parameters": [
            {"name": "name", "value": first_name},
            {"name": "order_number", "value": order_id},
            {"name": "total_price", "value": total_amount}
        ],
    }

    logger.info(f"[WhatsApp] Routing verified token schema payload to WATI for Order #{order_id}")

    try:
        response = requests.post(url, params=params, json=payload, headers=headers, timeout=25)
        logger.info(f"[WhatsApp] Response Status: {response.status_code} | Text: {response.text}")

        if response.status_code not in (200, 201):
            logger.error(f"[WhatsApp] Order #{order.id} failed with status {response.status_code}")
            return False

        result = response.json()
        if result.get("result") is True or result.get("result") == "success":
            return True

        logger.error(f"[WhatsApp] WATI verification rejected processing: {result}")
        return False

    except Exception as exc:
        logger.error(f"[WhatsApp] Order #{order.id} unexpected exception: {exc}", exc_info=True)
        return False