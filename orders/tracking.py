# orders/tracking.py
"""
Delhivery shipment tracking.

fetch_tracking()  — live status + scan history for one waybill (cached 10 min)
sync_order()      — move an order to Shipped / Delivered from its Delhivery
                    status and fire the matching WhatsApp messages. Used by
                    the `sync_delhivery_status` command (run from cron) and
                    the "Sync Delhivery status" admin action.
"""

import logging
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger("orders.services")

CACHE_SECONDS = 600

# Delhivery StatusType codes
_DELIVERED = {"DL"}
_RETURNED = {"RT"}


def _api():
    token = getattr(settings, "DELHIVERY_API_TOKEN", "")
    base = getattr(settings, "DELHIVERY_API_URL", "https://track.delhivery.com").rstrip("/")
    return token, base


def stage_of(status: str, status_type: str) -> str:
    """Collapse Delhivery's many statuses into the stages customers see."""
    s = (status or "").lower()
    t = (status_type or "").upper()
    if t in _DELIVERED or s == "delivered":
        return "delivered"
    if t in _RETURNED or "rto" in s or "return" in s:
        return "returned"
    if s == "dispatched" or "out for delivery" in s:
        return "out_for_delivery"
    if s in ("manifested", "not picked", "pickup scheduled", "open"):
        return "packed"
    return "in_transit"


def fetch_tracking(waybill: str, use_cache: bool = True) -> dict | None:
    """Return {status, status_type, stage, location, updated_at, instructions, scans[]}."""
    if not waybill:
        return None
    key = f"delhivery-track-{waybill}"
    if use_cache and (hit := cache.get(key)) is not None:
        return hit

    token, base = _api()
    if not token:
        logger.error("[Delhivery] DELHIVERY_API_TOKEN not configured")
        return None
    try:
        response = requests.get(
            f"{base}/api/v1/packages/json/",
            params={"waybill": waybill},
            headers={"Authorization": f"Token {token}", "Accept": "application/json"},
            timeout=15,
        )
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        logger.error(f"[Delhivery] Tracking {waybill} failed: {exc}")
        return None

    shipments = data.get("ShipmentData") or []
    if not shipments:
        logger.warning(f"[Delhivery] Tracking {waybill}: no ShipmentData — {str(data)[:300]}")
        return None

    shipment = shipments[0].get("Shipment", {})
    current = shipment.get("Status", {}) or {}
    scans = []
    for item in shipment.get("Scans", []) or []:
        scan = item.get("ScanDetail", {}) or {}
        scans.append({
            "status": scan.get("Scan", ""),
            "detail": scan.get("Instructions", ""),
            "location": scan.get("ScannedLocation", ""),
            "time": scan.get("ScanDateTime", ""),
        })
    scans.reverse()  # newest first

    result = {
        "status": current.get("Status", ""),
        "status_type": current.get("StatusType", ""),
        "stage": stage_of(current.get("Status", ""), current.get("StatusType", "")),
        "location": current.get("StatusLocation", ""),
        "updated_at": current.get("StatusDateTime", ""),
        "instructions": current.get("Instructions", ""),
        "expected_delivery": shipment.get("ExpectedDeliveryDate") or shipment.get("PromisedDeliveryDate") or "",
        "scans": scans,
    }
    cache.set(key, result, CACHE_SECONDS)
    return result


def sync_order(order) -> str | None:
    """
    Update one order from Delhivery. Returns the stage, or None when the
    shipment could not be read. Status changes trigger WhatsApp messages
    through the Order signals; out-for-delivery is sent from here because
    it is not an order status.
    """
    from .notifications import notify

    info = fetch_tracking(order.delhivery_waybill, use_cache=False)
    if not info:
        return None

    stage = info["stage"]
    note = f"{info['status']} — {info['location']} ({info['updated_at']})".strip(" —()")
    fields = {"tracking_note": note}
    if not order.tracking_link:
        fields["tracking_link"] = f"https://www.delhivery.com/track-v2/package/{order.delhivery_waybill}"

    if stage in ("in_transit", "out_for_delivery") and order.order_status in ("Pending", "Processing", "Confirmed"):
        fields["order_status"] = "Shipped"
    elif stage == "delivered" and order.order_status != "Delivered":
        fields["order_status"] = "Delivered"
        delivered = parse_datetime(info["updated_at"] or "") if info["updated_at"] else None
        if delivered and timezone.is_naive(delivered):  # Delhivery reports India time
            delivered = timezone.make_aware(delivered, ZoneInfo("Asia/Kolkata"))
        fields["delivered_at"] = delivered or timezone.now()

    for name, value in fields.items():
        setattr(order, name, value)
    # A full save() so the status-change signal sends Shipped / Delivered messages.
    order.save()

    if stage == "out_for_delivery":
        notify(order, "out_for_delivery")
    return stage
