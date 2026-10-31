"""
Product feed for Google Merchant Center (Shopping) and Meta Commerce Manager
(Facebook / Instagram shop and dynamic product ads).

GET /api/store/feeds/products.xml — RSS 2.0 with the Google `g:` namespace,
which both Google and Meta read. Item ids are product SKUs, the same ids the
website sends with ViewContent / AddToCart / Purchase.
"""
import re
from xml.sax.saxutils import escape

from django.conf import settings
from django.http import HttpResponse
from django.utils.html import strip_tags
from django.views.decorators.cache import cache_page

from .models import Product
from .warranty import plan_for_product

CATEGORY = [
    (re.compile(r'monitor', re.I), 'Electronics > Video > Computer Monitors'),
    (re.compile(r'desktop|mini pc|tiny|cpu|optiplex|thinkcentre|imac|thin client', re.I), 'Electronics > Computers > Desktop Computers'),
]
DEFAULT_CATEGORY = 'Electronics > Computers > Laptops'


def google_category(product) -> str:
    text = f"{product.category.name if product.category_id else ''} {product.title}"
    for pattern, path in CATEGORY:
        if pattern.search(text):
            return path
    return DEFAULT_CATEGORY


def _absolute(request, url: str) -> str:
    return url if url.startswith('http') else request.build_absolute_uri(url)


def feed_items(request):
    """(items, skipped_without_image) for active products."""
    site = getattr(settings, 'SITE_URL', 'https://www.yuvacomputers.in').rstrip('/')
    products = (Product.objects.filter(is_active=True)
                .select_related('brand', 'category', 'warranty_plan')
                .prefetch_related('images', 'variants'))
    cache, items, skipped = {}, [], 0
    for p in products:
        images = sorted(p.images.all(), key=lambda i: (not i.is_primary, i.order, i.id))
        if not images:
            skipped += 1   # Google and Meta reject products without a photo
            continue
        stock = p.stock if p.stock_mode == 'model' else sum(v.stock for v in p.variants.all())
        price, original = p.price, p.original_price
        plan = plan_for_product(p, cache)
        description = strip_tags(p.description or '').strip() or p.title
        if plan:
            description = f"{description} {plan.summary}."
        items.append({
            'id': p.sku,
            'title': p.title[:150],
            'description': description[:5000],
            'link': f"{site}/product/{p.slug}",
            'image_link': _absolute(request, images[0].image.url),
            'additional_image_link': [_absolute(request, i.image.url) for i in images[1:11]],
            'availability': 'in_stock' if stock > 0 else 'out_of_stock',
            'price': f"{(original if original and original > price else price):.2f} INR",
            'sale_price': f"{price:.2f} INR" if original and original > price else '',
            'condition': 'refurbished',
            'brand': p.brand.name if p.brand_id else 'Yuva Computers',
            'identifier_exists': 'no',
            'google_product_category': google_category(p),
            'product_type': p.category.name if p.category_id else '',
            'custom_label_0': plan.badge if plan else '',
            'custom_label_1': p.get_condition_display(),
        })
    return items, skipped


@cache_page(60 * 15)
def products_feed(request):
    items, skipped = feed_items(request)
    site = getattr(settings, 'SITE_URL', 'https://www.yuvacomputers.in').rstrip('/')
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">',
        '<channel>',
        '<title>Yuva Computers</title>',
        f'<link>{escape(site)}</link>',
        f'<description>Certified refurbished laptops and desktops. {len(items)} products; '
        f'{skipped} left out until they have a photo.</description>',
    ]
    for item in items:
        out.append('<item>')
        for key, value in item.items():
            if key in ('title', 'description', 'link'):
                out.append(f'<{key}>{escape(value)}</{key}>')
            elif isinstance(value, list):
                out.extend(f'<g:{key}>{escape(v)}</g:{key}>' for v in value)
            elif value:
                out.append(f'<g:{key}>{escape(str(value))}</g:{key}>')
        out.append('</item>')
    out += ['</channel>', '</rss>']
    return HttpResponse('\n'.join(out), content_type='application/xml; charset=utf-8')
