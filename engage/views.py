import logging
import re
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models import F
from django.utils import timezone
from rest_framework import permissions, serializers
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from orders.models import Order, OrderItem
from store.models import Coupon, Product, ProductVariant

from .models import CartSnapshot, StockAlert, TradeInRequest

logger = logging.getLogger("orders.services")


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _valid_phone(value) -> str | None:
    phone = _digits(value)[-10:]
    return phone if len(phone) == 10 and phone[0] in "6789" else None


class FormThrottle(AnonRateThrottle):
    """Public forms: stop bots from flooding the shop with fake leads.

    Own scope, so it counts form submissions only. Sharing the default 'anon'
    scope would count every page a visitor browses and block the forms.
    """
    scope = 'engage_forms'
    rate = '30/hour'


# ── Delivery estimate by pincode ─────────────────────────────────────────────

# (pincode prefixes, min days, max days) from Hyderabad. First match wins.
DELIVERY_ZONES = [
    (('500', '501', '502'), 1, 2),                       # Hyderabad & surroundings
    (('50', '51', '52', '53'), 2, 4),                    # Telangana & Andhra Pradesh
    (('56', '57', '58', '59', '60', '61', '62', '63', '64', '67', '68', '69', '40', '41', '42', '43', '44'), 3, 5),
    (('18', '19', '78', '79', '744', '682'), 6, 10),     # J&K, HP, North-East, islands
]
DEFAULT_ZONE = (4, 7)


def estimate_days(pin: str) -> tuple[int, int]:
    for prefixes, low, high in DELIVERY_ZONES:
        if pin.startswith(prefixes):
            return low, high
    return DEFAULT_ZONE


def delhivery_pincode(pin: str) -> dict | None:
    """Delhivery serviceability for one pincode, or None if Delhivery can't be reached."""
    token = getattr(settings, "DELHIVERY_API_TOKEN", "")
    base = getattr(settings, "DELHIVERY_API_URL", "https://track.delhivery.com").rstrip("/")
    if not token:
        return None
    try:
        response = requests.get(
            f"{base}/c/api/pin-codes/json/",
            params={"filter_codes": pin},
            headers={"Authorization": f"Token {token}", "Accept": "application/json"},
            timeout=10,
        )
        if response.status_code != 200:
            logger.warning(f"[Pincode] {pin}: HTTP {response.status_code}")
            return None
        codes = response.json().get("delivery_codes") or []
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"[Pincode] {pin}: {exc}")
        return None
    if not codes:
        return {"serviceable": False}
    info = codes[0].get("postal_code", {})
    return {
        "serviceable": info.get("pre_paid") == "Y" or info.get("cod") == "Y",
        "cod": info.get("cod") == "Y",
        "city": (info.get("city") or info.get("district") or "").title(),
        "state": info.get("state_code") or "",
    }


class PincodeCheckView(APIView):
    """GET /api/engage/pincode/?pin=500060 → serviceability + approximate delivery days."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        pin = _digits(request.query_params.get("pin"))
        if len(pin) != 6 or pin[0] == "0":
            return Response({"error": "Enter a valid 6-digit pincode."}, status=400)

        key = f"pincode:{pin}"
        if (hit := cache.get(key)) is not None:
            return Response(hit)

        courier = delhivery_pincode(pin)
        low, high = estimate_days(pin)
        if courier is None:  # Delhivery unreachable: give the estimate, assume deliverable
            result = {"pin": pin, "serviceable": True, "verified": False, "cod": None, "city": "",
                      "min_days": low, "max_days": high}
        else:
            result = {"pin": pin, "verified": True, "min_days": low, "max_days": high,
                      "cod": courier.get("cod", False), "city": courier.get("city", ""),
                      "serviceable": courier["serviceable"]}
            cache.set(key, result, 60 * 60 * 24)
        return Response(result)


# ── Back-in-stock requests ───────────────────────────────────────────────────

class StockAlertView(APIView):
    """POST /api/engage/stock-alerts/ {product, variant?, phone, name?}"""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [FormThrottle]

    def post(self, request):
        phone = _valid_phone(request.data.get("phone"))
        if not phone:
            return Response({"error": "Enter a valid 10-digit mobile number."}, status=400)
        product = Product.objects.filter(pk=request.data.get("product"), is_active=True).first()
        if not product:
            return Response({"error": "Product not found."}, status=404)
        variant = None
        if request.data.get("variant"):
            variant = ProductVariant.objects.filter(pk=request.data.get("variant"), product=product).first()

        StockAlert.objects.get_or_create(
            product=product, variant=variant, phone=phone, notified_at__isnull=True,
            defaults={"name": str(request.data.get("name", ""))[:100]},
        )
        return Response({"ok": True, "message": "Done! We'll WhatsApp you as soon as it's back in stock."}, status=201)


# ── Saved cart (for one WhatsApp reminder) ───────────────────────────────────

class CartSnapshotView(APIView):
    """PUT the logged-in customer's cart; DELETE once they order or empty it."""
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request):
        items = request.data.get("items") or []
        if not isinstance(items, list):
            return Response({"error": "items must be a list"}, status=400)
        clean = [
            {
                "product_id": i.get("product_id"),
                "variant_id": i.get("variant_id"),
                "title": str(i.get("title", ""))[:200],
                "quantity": int(i.get("quantity") or 1),
                "price": float(i.get("price") or 0),
            }
            for i in items[:20] if isinstance(i, dict)
        ]
        if not clean:
            CartSnapshot.objects.filter(user=request.user).delete()
            return Response({"ok": True})
        total = sum(i["price"] * i["quantity"] for i in clean)
        snapshot, created = CartSnapshot.objects.get_or_create(user=request.user, defaults={"items": clean, "total": total})
        if not created:
            changed = snapshot.items != clean
            snapshot.items, snapshot.total = clean, total
            if changed:
                snapshot.reminded_at = None  # a new cart can be reminded once again
            snapshot.save()
        return Response({"ok": True})

    def delete(self, request):
        CartSnapshot.objects.filter(user=request.user).delete()
        return Response({"ok": True})


# ── Sell / exchange old laptop ───────────────────────────────────────────────

class TradeInSerializer(serializers.ModelSerializer):
    class Meta:
        model = TradeInRequest
        fields = [
            "id", "name", "phone", "city", "brand", "model_name", "processor", "ram", "storage",
            "condition", "has_charger", "wants_exchange", "notes", "photo_1", "photo_2", "photo_3",
            "estimate_low", "estimate_high",
        ]

    def validate_phone(self, value):
        phone = _valid_phone(value)
        if not phone:
            raise serializers.ValidationError("Enter a valid 10-digit mobile number.")
        return phone

    def validate(self, attrs):
        for field in ("photo_1", "photo_2", "photo_3"):
            photo = attrs.get(field)
            if photo and photo.size > 8 * 1024 * 1024:
                raise serializers.ValidationError({field: "Each photo must be under 8 MB."})
        return attrs


class TradeInView(APIView):
    """POST /api/engage/trade-in/ (multipart, photos optional)."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [FormThrottle]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = TradeInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        return Response({"ok": True, "id": obj.id}, status=201)


# ── Warranty lookup ──────────────────────────────────────────────────────────




def _add_months(dt, months: int):
    year, month = divmod(dt.month - 1 + months, 12)
    year, month = dt.year + year, month + 1
    for day in (dt.day, 30, 29, 28):
        try:
            return dt.replace(year=year, month=month, day=day)
        except ValueError:
            continue
    return dt


def coverage(plan, start, today) -> dict:
    """Warranty dates for a plan starting on `start` (a date)."""
    if plan is None:
        return {"status": "active", "warranty_until": None, "days_left": None,
                "replacement_until": None, "replacement_open": False}
    replacement_end = start + timedelta(days=plan.testing_days) if plan.testing_days else None
    months = plan.parts_months or (plan.service_months if plan.free_service else 0)
    if months:
        end = _add_months(start, months)
    elif replacement_end:
        end = replacement_end
    else:
        end = None
    return {
        "replacement_until": replacement_end,
        "replacement_open": bool(replacement_end and today <= replacement_end),
        "warranty_until": end,
        "days_left": max((end - today).days, 0) if end else None,
        "status": "no_warranty" if end is None else ("active" if today <= end else "expired"),
    }


def _plan_fields(plan) -> dict:
    from store.warranty import plan_data

    return {"warranty_period": plan.name if plan else "Warranty", "plan": plan_data(plan)}


def warranty_for_item(item: OrderItem, cache=None) -> dict:
    from store.warranty import plan_for_product, plan_for_purchase

    order = item.order
    plan = plan_for_product(item.product, cache) if item.product else plan_for_purchase(item.product_name, item.price, cache)
    start = order.delivered_at
    result = {
        "source": "online",
        "product": item.product_name,
        "variant": item.variant_label,
        "serial_number": item.serial_number,
        "order_id": order.id,
        "order_status": order.order_status,
        "store": "",
        "purchased_on": order.created_at.date(),
        "delivered_on": start.date() if start else None,
        **_plan_fields(plan),
        "status": "not_started",
        "warranty_until": None,
        "days_left": None,
        "replacement_until": None,
        "replacement_open": False,
    }
    if order.order_status == "Cancelled":
        result["status"] = "cancelled"
        return result
    if not start:
        return result  # warranty starts on delivery
    result.update(coverage(plan, start.date(), timezone.localdate()))
    return result


def warranty_for_store_purchase(purchase, cache=None) -> dict:
    from store.warranty import plan_for_purchase

    plan = plan_for_purchase(purchase.model_name, purchase.amount, cache)
    result = {
        "source": "store",
        "product": purchase.model_name or "Laptop",
        "variant": "",
        "serial_number": "",
        "order_id": None,
        "order_status": "Delivered",
        "store": purchase.store,
        "purchased_on": purchase.sale_date,
        "delivered_on": purchase.sale_date,
        **_plan_fields(plan),
    }
    result.update(coverage(plan, purchase.sale_date, timezone.localdate()))
    return result


class WarrantyLookupView(APIView):
    """GET ?serial=ABC123  or  ?order_id=123&phone=9876543210  or  ?phone=9876543210 (all purchases)."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []
    throttle_classes = [FormThrottle]

    def get(self, request):
        from .models import CustomerPurchase

        cache = {}
        serial = re.sub(r"[^A-Za-z0-9-]", "", request.query_params.get("serial", ""))
        items = OrderItem.objects.select_related("order", "product")
        found = []
        if serial:
            if len(serial) < 4:
                return Response({"error": "Enter the full serial number."}, status=400)
            found = [warranty_for_item(i, cache) for i in items.filter(serial_number__iexact=serial)[:10]]
            if not found:
                return Response({"error": "No laptop found with that serial number. Try your phone number instead."}, status=404)
        else:
            order_id = _digits(request.query_params.get("order_id"))
            phone = _valid_phone(request.query_params.get("phone"))
            if not phone:
                return Response({"error": "Enter the 10-digit phone number you gave at purchase."}, status=400)
            if order_id:
                order = Order.objects.filter(pk=order_id).first()
                if not order or _digits(order.phone)[-10:] != phone:
                    return Response({"error": "We couldn't find an order with that number and phone."}, status=404)
                found = [warranty_for_item(i, cache) for i in items.filter(order=order)[:10]]
            else:
                online = items.filter(order__phone__endswith=phone).order_by("-order__created_at")[:10]
                store = CustomerPurchase.objects.filter(phone=phone).order_by("-sale_date")[:10]
                found = [warranty_for_item(i, cache) for i in online] + [warranty_for_store_purchase(p, cache) for p in store]
            if not found:
                return Response({"error": "We couldn't find a purchase with that phone number. WhatsApp us and we'll check for you."}, status=404)
        return Response({"items": found[:10]})


# ── Google reviews ───────────────────────────────────────────────────────────

class GoogleReviewsView(APIView):
    """Rating + latest reviews from the Google Business profile (cached 12 h)."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        key = getattr(settings, "GOOGLE_PLACES_API_KEY", "")
        place_id = getattr(settings, "GOOGLE_PLACE_ID", "")
        if not key or not place_id:
            return Response({"available": False})
        if (hit := cache.get("google_reviews")) is not None:
            return Response(hit)
        try:
            response = requests.get(
                f"https://places.googleapis.com/v1/places/{place_id}",
                params={"languageCode": "en"},
                headers={"X-Goog-Api-Key": key,
                         "X-Goog-FieldMask": "rating,userRatingCount,reviews,googleMapsUri"},
                timeout=10,
            )
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning(f"[GoogleReviews] {exc}")
            return Response({"available": False})
        if response.status_code != 200:
            logger.warning(f"[GoogleReviews] HTTP {response.status_code}: {str(data)[:300]}")
            return Response({"available": False})
        reviews = [
            {
                "author": (r.get("authorAttribution") or {}).get("displayName", "Google user"),
                "photo": (r.get("authorAttribution") or {}).get("photoUri", ""),
                "rating": r.get("rating", 5),
                "text": ((r.get("text") or r.get("originalText") or {}).get("text") or "").strip(),
                "when": r.get("relativePublishTimeDescription", ""),
            }
            for r in data.get("reviews", [])
        ]
        result = {
            "available": True,
            "rating": data.get("rating"),
            "total": data.get("userRatingCount"),
            "url": data.get("googleMapsUri", ""),
            "reviews": [r for r in reviews if r["rating"] >= 4 and r["text"]],
        }
        cache.set("google_reviews", result, 60 * 60 * 12)
        return Response(result)


# ── Public offers (coupons) ──────────────────────────────────────────────────

class OffersView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        now = timezone.now()
        coupons = Coupon.objects.filter(
            active=True, is_public=True, valid_from__lte=now, valid_to__gte=now, uses_count__lt=F("usage_limit"),
        ).order_by("min_order_value")
        return Response([
            {
                "code": c.code,
                "description": c.description or (
                    f"{c.value:g}% off" if c.discount_type == "percentage" else f"₹{c.value:,.0f} off"
                ),
                "discount_type": c.discount_type,
                "value": float(c.value),
                "min_order_value": float(c.min_order_value),
                "first_order_only": c.first_order_only,
                "valid_to": c.valid_to,
            }
            for c in coupons
        ])
