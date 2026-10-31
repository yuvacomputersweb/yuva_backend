"""
Server-side Purchase events for Meta (Conversions API).

The browser pixel misses purchases when it is blocked (ad blockers, iOS).
Sending the same Purchase from the server, with the same event id
(`order_<id>`) as the browser, lets Meta count every order exactly once.

Settings: META_PIXEL_ID, META_CAPI_TOKEN (Events Manager → Settings →
Conversions API → Generate access token). Without a token nothing is sent.
"""
import hashlib
import logging
import re
import time

import requests
from django.conf import settings

logger = logging.getLogger("orders.services")


def _hash(value: str) -> str:
    value = (value or '').strip().lower()
    return hashlib.sha256(value.encode()).hexdigest() if value else ''


def _phone(value: str) -> str:
    digits = re.sub(r'\D', '', value or '')[-10:]
    return f'91{digits}' if len(digits) == 10 else ''


def purchase_payload(order) -> dict:
    tracking = order.tracking or {}
    user = {
        'em': _hash(order.email or getattr(order.user, 'email', '')),
        'ph': _hash(_phone(order.phone)),
        'fn': _hash(order.first_name),
        'ln': _hash(order.last_name),
        'ct': _hash(re.sub(r'\s+', '', order.city or '')),
        'st': _hash(re.sub(r'\s+', '', order.state or '')),
        'zp': _hash(order.zip_code),
        'country': _hash('in'),
        'external_id': _hash(str(order.user_id or '')),
    }
    user_data = {k: [v] for k, v in user.items() if v}
    for key, field in (('ip', 'client_ip_address'), ('ua', 'client_user_agent'), ('fbp', 'fbp'), ('fbc', 'fbc')):
        if tracking.get(key):
            user_data[field] = tracking[key]

    items = list(order.items.select_related('product'))
    site = getattr(settings, 'SITE_URL', 'https://www.yuvacomputers.in').rstrip('/')
    return {
        'event_name': 'Purchase',
        'event_time': int(time.time()),
        'event_id': f'order_{order.id}',
        'action_source': 'website',
        'event_source_url': f'{site}/checkout',
        'user_data': user_data,
        'custom_data': {
            'currency': 'INR',
            'value': float(order.total_amount),
            'order_id': str(order.id),
            'content_type': 'product',
            'content_ids': [i.product.sku if i.product else str(i.product_id) for i in items],
            'contents': [
                {'id': i.product.sku if i.product else str(i.product_id), 'quantity': i.quantity, 'item_price': float(i.price)}
                for i in items
            ],
            'num_items': sum(i.quantity for i in items),
        },
    }


def send_purchase(order) -> bool:
    """Send once per order. Never raises."""
    pixel = getattr(settings, 'META_PIXEL_ID', '')
    token = getattr(settings, 'META_CAPI_TOKEN', '')
    if not pixel or not token:
        return False
    tracking = dict(order.tracking or {})
    if tracking.get('meta_purchase_sent'):
        return False
    try:
        body = {'data': [purchase_payload(order)]}
        test_code = getattr(settings, 'META_CAPI_TEST_CODE', '')
        if test_code:
            body['test_event_code'] = test_code
        version = getattr(settings, 'META_GRAPH_VERSION', 'v22.0')
        response = requests.post(
            f'https://graph.facebook.com/{version}/{pixel}/events',
            params={'access_token': token}, json=body, timeout=15,
        )
        ok = response.status_code == 200
    except (requests.RequestException, ValueError) as exc:
        logger.warning(f"[MetaCAPI] Order #{order.id}: {exc}")
        return False
    if ok:
        tracking['meta_purchase_sent'] = True
        type(order).objects.filter(pk=order.pk).update(tracking=tracking)
        order.tracking = tracking
        logger.info(f"[MetaCAPI] Order #{order.id} Purchase sent")
    else:
        logger.warning(f"[MetaCAPI] Order #{order.id}: HTTP {response.status_code} {response.text[:300]}")
    return ok
