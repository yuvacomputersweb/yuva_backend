"""
Which warranty plan applies to a product.

Automatic rules (a plan picked on the product always wins):
  Apple (MacBook / iMac)            → apple     6-month free service, 2 h battery
  Monitors                          → monitor   tested, no warranty
  Dedicated graphics (NVIDIA, etc.) → graphics  6-month free service
  Price under ₹15,000               → basic     15-day testing + free service
  Everything else                   → standard  1-year RAM, SSD & motherboard
"""
import re
from decimal import Decimal

STANDARD_MIN_PRICE = Decimal('15000')

_APPLE = re.compile(r'\b(apple|macbook|imac|mac\s*mini|mac\s*studio)\b', re.I)
_MONITOR = re.compile(r'\bmonitors?\b', re.I)
_GPU = re.compile(
    r'nvidia|geforce|quadro|\brtx\b|\bgtx\b|\bmx\s?\d{3}\b|radeon\s*(rx|pro)|'
    r'\b\d+\s*gb\s*(dedicated|graphics|gddr\d?)\b|dedicated\s+graphics',
    re.I,
)


def auto_plan_code(*, brand='', category='', title='', graphics='', price=None) -> str:
    if _APPLE.search(f'{brand} {title}'):
        return 'apple'
    if _MONITOR.search(f'{category} {title}'):
        return 'monitor'
    graphics = graphics or ''
    gpu_text = title if 'integrated' in graphics.lower() else f'{graphics} {title}'
    if _GPU.search(gpu_text):
        return 'graphics'
    if price is not None and Decimal(str(price)) < STANDARD_MIN_PRICE:
        return 'basic'
    return 'standard'


def plans_by_code(cache=None) -> dict:
    """All plans keyed by code. Pass a dict (e.g. serializer context) to reuse it."""
    from .models import WarrantyPlan

    if cache is not None and 'warranty_plans' in cache:
        return cache['warranty_plans']
    plans = {p.code: p for p in WarrantyPlan.objects.all()}
    if cache is not None:
        cache['warranty_plans'] = plans
    return plans


def plan_for_product(product, cache=None):
    if product.warranty_plan_id:
        return product.warranty_plan
    code = auto_plan_code(
        brand=product.brand.name if product.brand_id else '',
        category=product.category.name if product.category_id else '',
        title=product.title, graphics=product.graphics, price=product.price,
    )
    return plans_by_code(cache).get(code)


def plan_for_purchase(model_name: str, amount=None, cache=None):
    """Store sales only have free text, so guess from the model name and price."""
    code = auto_plan_code(title=model_name or '', price=amount)
    return plans_by_code(cache).get(code)


def plan_data(plan) -> dict | None:
    if plan is None:
        return None
    return {
        'code': plan.code,
        'name': plan.name,
        'badge': plan.badge,
        'summary': plan.summary,
        'testing_days': plan.testing_days,
        'parts_months': plan.parts_months,
        'free_service': plan.free_service,
        'service_months': plan.service_months,
        'battery_hours': plan.battery_hours,
        'points': [line.strip() for line in plan.points.splitlines() if line.strip()],
    }
