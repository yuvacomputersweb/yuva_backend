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

from .notifications import format_wati_phone as _format_e164  # noqa: F401  (old name)


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

    # ── WhatsApp "order placed" (logged + de-duplicated in OrderNotification)
    if not order.whatsapp_sent:
        from .notifications import notify
        notify(order, "order_placed")
    else:
        logger.info(f"[WhatsApp] Order #{order.id} already notified — skipping")

    # Delhivery now has a waybill: give the customer a tracking link right away.
    if order.delhivery_waybill and not order.tracking_link:
        order.tracking_link = f"https://www.delhivery.com/track-v2/package/{order.delhivery_waybill}"
        order.save(update_fields=["tracking_link"])

    # Server-side Purchase for Meta ads (sent once; never blocks the order).
    try:
        from .meta_capi import send_purchase
        send_purchase(order)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[MetaCAPI] Order #{order.id}: {exc}")



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

    ret = getattr(settings, "DELHIVERY_RETURN_ADDRESS", {
        "address": "Sai Towers, 204, 2nd Floor, Metro Pillar No. 1519, Dilsukhnagar",
        "city": "Hyderabad", "state": "Telangana", "pin": "500060", "phone": "9709888456",
    })

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
                "seller_add":      ret["address"],
                "seller_inv":      str(order.id),
                # Returns (RTO) come back to the store — set in settings / env.
                "return_pin":      ret["pin"],
                "return_city":     ret["city"],
                "return_phone":    ret["phone"],
                "return_name":     "Yuva Computers",
                "return_add":      ret["address"],
                "return_state":    ret["state"],
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
    """Kept for compatibility — use orders.notifications.notify()."""
    from .notifications import notify
    return notify(order, "order_placed")
