#store/views
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticatedOrReadOnly
from rest_framework.parsers import MultiPartParser, FormParser
from django.db.models import Q, Avg
from decimal import Decimal
from django.utils import timezone

from .models import (
    Brand, Category, UsageTag, Product,
    ProductImage, Review, SiteConfig, Coupon
)
from .serializers import (
    BrandSerializer, CategorySerializer, UsageTagSerializer,
    ProductListSerializer, ProductDetailSerializer,
    ReviewSerializer, SiteConfigSerializer, ProductSearchSerializer
)


class BrandListView(generics.ListAPIView):
    serializer_class = BrandSerializer
    queryset = Brand.objects.all()
    permission_classes = [AllowAny]


class CategoryListView(generics.ListAPIView):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    permission_classes = [AllowAny]


class UsageTagListView(generics.ListAPIView):
    serializer_class = UsageTagSerializer
    queryset = UsageTag.objects.all()
    permission_classes = [AllowAny]


class ProductListView(generics.ListAPIView):
    serializer_class = ProductListSerializer
    permission_classes = [AllowAny]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    def get_queryset(self):
        qs = Product.objects.filter(is_active=True).prefetch_related(
            'images', 'variants', 'usage_tags'
        ).select_related('category', 'brand')

        # ── Existing filters ──────────────────────────────────────────────────
        category = self.request.query_params.get('category')
        brand = self.request.query_params.get('brand')
        usage = self.request.query_params.get('usage')
        condition = self.request.query_params.get('condition')
        is_new_arrival = self.request.query_params.get('is_new_arrival')
        is_best_seller = self.request.query_params.get('is_best_seller')
        is_trending = self.request.query_params.get('is_trending')
        is_best_deal = self.request.query_params.get('is_best_deal')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        search = self.request.query_params.get('search')

        # ── NEW: variant-level filters ────────────────────────────────────────
        # Supports comma-separated values for multi-select, e.g. processor=i5,i7
        variant_processor = self.request.query_params.get('processor')
        variant_ram = self.request.query_params.get('ram')
        variant_storage = self.request.query_params.get('storage')

        if category:
            qs = qs.filter(category__slug=category)
        if brand:
            qs = qs.filter(brand__slug=brand)
        if usage:
            qs = qs.filter(usage_tags__slug=usage)
        if condition:
            qs = qs.filter(condition=condition)
        if is_new_arrival == 'true':
            qs = qs.filter(is_new_arrival=True)
        if is_best_seller == 'true':
            qs = qs.filter(is_best_seller=True)
        if is_trending == 'true':
            qs = qs.filter(is_trending=True)
        if is_best_deal == 'true':
            qs = qs.filter(is_best_deal=True)
        if min_price:
            qs = qs.filter(price__gte=min_price)
        if max_price:
            qs = qs.filter(price__lte=max_price)
        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(sku__icontains=search) |
                Q(brand__name__icontains=search) |
                Q(processor__icontains=search)
            ).distinct()

        # Variant-level filtering — filter through related variants
        # Supports multi-value via comma separation: ?processor=i5,i7
        if variant_processor:
            values = [v.strip() for v in variant_processor.split(',') if v.strip()]
            q = Q()
            for val in values:
                q |= Q(variants__processor__icontains=val)
            qs = qs.filter(q)

        if variant_ram:
            values = [v.strip() for v in variant_ram.split(',') if v.strip()]
            q = Q()
            for val in values:
                q |= Q(variants__ram__icontains=val)
            qs = qs.filter(q)

        if variant_storage:
            values = [v.strip() for v in variant_storage.split(',') if v.strip()]
            q = Q()
            for val in values:
                q |= Q(variants__storage__icontains=val)
            qs = qs.filter(q)

        # Always use distinct() to prevent duplicate products from variant JOINs
        return qs.distinct().order_by('-created_at')


class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True).prefetch_related(
        'images', 'variants', 'usage_tags', 'reviews'
    ).select_related('category', 'brand')
    serializer_class = ProductDetailSerializer
    lookup_field = 'slug'
    permission_classes = [AllowAny]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx


class ReviewListCreateView(generics.ListCreateAPIView):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        return Review.objects.filter(product__slug=self.kwargs['slug']).order_by('-created_at')

    def perform_create(self, serializer):
        product = Product.objects.get(slug=self.kwargs['slug'])
        user = self.request.user
        user_name = "Anonymous"
        if user.is_authenticated:
            user_name = f"{user.first_name} {user.last_name}".strip() or user.username
        variant_info = self.request.data.get('variant_info', 'Standard Variant')
        serializer.save(product=product, user_name=user_name, variant_info=variant_info)


class HomeDataView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        ctx = {'request': request}
        return Response({
            'new_arrivals': ProductListSerializer(
                Product.objects.filter(is_new_arrival=True, is_active=True)[:10],
                many=True, context=ctx
            ).data,
            'best_sellers': ProductListSerializer(
                Product.objects.filter(is_best_seller=True, is_active=True)[:10],
                many=True, context=ctx
            ).data,
            'trending': ProductListSerializer(
                Product.objects.filter(is_trending=True, is_active=True)[:10],
                many=True, context=ctx
            ).data,
            'best_deals': ProductListSerializer(
                Product.objects.filter(is_best_deal=True, is_active=True)[:10],
                many=True, context=ctx
            ).data,
            'categories': CategorySerializer(
                Category.objects.filter(is_featured=True),
                many=True,
                context=ctx
            ).data,
        })


class SiteConfigView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        config = SiteConfig.objects.first()
        if not config:
            config = SiteConfig.objects.create()
        return Response(SiteConfigSerializer(config).data)


class GlobalSearchView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        q = request.query_params.get('q', '').strip()
        if len(q) < 1:
            return Response({
                'products': [],
                'categories': [],
                'brands': [],
                'message': 'Enter search term'
            })

        search_query = (
            Q(title__icontains=q) |
            Q(sku__icontains=q) |
            Q(brand__name__icontains=q) |
            Q(category__name__icontains=q) |
            Q(processor__icontains=q) |
            Q(ram__icontains=q) |
            Q(storage__icontains=q) |
            Q(description__icontains=q)
        )

        products = Product.objects.filter(
            search_query,
            is_active=True
        ).select_related('category', 'brand').prefetch_related('images')[:8]

        categories = Category.objects.filter(name__icontains=q)[:6]
        brands = Brand.objects.filter(name__icontains=q)[:6]

        return Response({
            'products': ProductSearchSerializer(products, many=True, context={'request': request}).data,
            'categories': CategorySerializer(categories, many=True).data,
            'brands': BrandSerializer(brands, many=True).data,
            'has_more': Product.objects.filter(is_active=True).count() > 8,
            'term': q
        })


class ValidateCouponView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        code = request.data.get('code', '').strip().upper()
        order_total = Decimal(str(request.data.get('order_total', 0)))

        if not code:
            return Response(
                {'error': 'Coupon code is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            coupon = Coupon.objects.get(code=code, active=True)
            now = timezone.now()

            if coupon.valid_from > now or coupon.valid_to < now:
                return Response(
                    {'error': 'This coupon has expired'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if coupon.uses_count >= coupon.usage_limit:
                return Response(
                    {'error': 'Coupon usage limit reached'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if order_total < coupon.min_order_value:
                return Response(
                    {'error': f'Minimum order of ₹{coupon.min_order_value} required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if coupon.first_order_only:
                from orders.models import Order
                if not request.user.is_authenticated:
                    return Response({'error': 'Log in to use this first-order coupon'}, status=status.HTTP_400_BAD_REQUEST)
                if Order.objects.filter(user=request.user, payment_status__in=['Paid', 'Deposit Paid']).exists():
                    return Response({'error': 'This coupon is only for your first order'}, status=status.HTTP_400_BAD_REQUEST)

            discount = (
                (order_total * coupon.value / 100)
                if coupon.discount_type == 'percentage'
                else coupon.value
            )

            return Response({
                'success': True,
                'code': coupon.code,
                'discount': float(discount),
                'message': f'Coupon applied! You save ₹{discount:.0f}',
            })

        except Coupon.DoesNotExist:
            return Response(
                {'error': 'Invalid coupon code'},
                status=status.HTTP_404_NOT_FOUND
            )


class CategoryBrandListView(generics.ListAPIView):
    serializer_class = BrandSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        category_slug = self.kwargs.get('slug')
        return Brand.objects.filter(products__category__slug=category_slug).distinct()


def _flag(value) -> bool:
    """JSON true/false, or the strings "true"/"1"/"yes"."""
    if isinstance(value, str):
        return value.strip().lower() in ('1', 'true', 'yes', 'on')
    return bool(value)


def _stock_sync_denied(request):
    """None when the X-Stock-Sync-Token header matches settings.STOCK_SYNC_TOKEN, else the error response."""
    import secrets
    from django.conf import settings

    expected = getattr(settings, 'STOCK_SYNC_TOKEN', '') or ''
    if not expected:
        return Response({'error': 'Stock sync is switched off (STOCK_SYNC_TOKEN not set)'},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    given = request.headers.get('X-Stock-Sync-Token', '') or ''
    if not secrets.compare_digest(given.encode(), expected.encode()):
        return Response({'error': 'Invalid token'}, status=status.HTTP_403_FORBIDDEN)
    return None


class StockSyncView(APIView):
    """
    Stock pushed from the shop's stock app. Only stock counts change.

    POST /api/store/stock-sync/
    Header:  X-Stock-Sync-Token: <settings.STOCK_SYNC_TOKEN>
    Body:    {"items": [{"product_sku": "DELL-5420", "stock": 3},                 # whole model
                        {"product_sku": "MBP-M1-14", "ram": "16GB", "storage": "512GB SSD", "stock": 1},
                        {"id": 11, "stock": 4}],                                  # a variant id
              "dry_run": false, "force": false}

    Most laptops keep one count for the model (Product.stock_mode == 'model'):
    RAM/SSD are upgraded to order, so every configuration sells from it. Send
    one row per model with just `product_sku` and `stock`. A row that names a
    configuration of such a product also sets the model's count.

    Products with stock_mode == 'variant' (MacBooks) keep a count per
    configuration: send `id`, or product SKU + processor + RAM + storage (the
    same keys as the admin Excel import).

    Counts are saved with save(update_fields=["stock"]) so the back-in-stock
    and low-stock WhatsApp messages still go out.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    MAX_ITEMS = 2000
    # Refuse a push that would suddenly sell out at least this many stock
    # counts *and* more than this share of everything in stock (likely a
    # broken list), unless the request sends "force": true.
    MASS_SELLOUT_MIN = 5
    MASS_SELLOUT_SHARE = 0.5

    def post(self, request):
        import logging
        from django.db import transaction
        from .models import Product, ProductVariant

        denied = _stock_sync_denied(request)
        if denied:
            return denied

        items = request.data.get('items') if isinstance(request.data, dict) else None
        if not isinstance(items, list):
            return Response({'error': '"items" must be a list'}, status=status.HTTP_400_BAD_REQUEST)
        if len(items) > self.MAX_ITEMS:
            return Response({'error': f'Too many items (max {self.MAX_ITEMS})'}, status=status.HTTP_400_BAD_REQUEST)
        dry_run = _flag(request.data.get('dry_run', False))
        force = _flag(request.data.get('force', False))

        plan, not_found, errors, seen = [], [], [], set()
        unchanged = 0
        variants = ProductVariant.objects.select_related('product')
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append({'index': i, 'error': 'item must be an object'})
                continue
            try:
                stock = int(item.get('stock'))
            except (TypeError, ValueError):
                errors.append({'index': i, 'error': '"stock" must be a whole number'})
                continue
            if stock < 0:
                errors.append({'index': i, 'error': '"stock" cannot be negative'})
                continue

            sku = str(item.get('product_sku') or '').strip()
            names_config = any(str(item.get(k) or '').strip() for k in ('processor', 'ram', 'storage'))
            target = None   # the object whose `stock` this row sets
            if item.get('id') not in (None, ''):
                try:
                    variant = variants.filter(id=int(item['id'])).first()
                except (TypeError, ValueError):
                    errors.append({'index': i, 'error': '"id" must be a number'})
                    continue
                if variant:
                    target = variant.product if variant.shares_model_stock else variant
            elif sku and not names_config:
                product = Product.objects.filter(sku=sku).first()
                if product and product.stock_mode == 'variant':
                    errors.append({'index': i, 'product_sku': sku,
                                   'error': 'this product has a separate count per configuration; send ram and storage'})
                    continue
                target = product
            elif sku:
                variant = variants.filter(
                    product__sku=sku,
                    processor=str(item.get('processor') or '').strip(),
                    ram=str(item.get('ram') or '').strip(),
                    storage=str(item.get('storage') or '').strip(),
                ).first()
                if variant:
                    target = variant.product if variant.shares_model_stock else variant
            if target is None:
                not_found.append({'index': i, **{k: item.get(k) for k in ('id', 'product_sku', 'processor', 'ram', 'storage') if item.get(k) not in (None, '')}})
                continue

            key = (type(target).__name__, target.pk)
            if key in seen:
                errors.append({'index': i, 'product_sku': sku or getattr(target, 'sku', ''),
                               'error': 'this stock count was already set by an earlier row; only the first was used'})
                continue
            seen.add(key)

            if target.stock == stock:
                unchanged += 1
                continue
            plan.append((target, stock))

        in_stock = (Product.objects.filter(stock_mode='model', stock__gt=0).count()
                    + ProductVariant.objects.filter(product__stock_mode='variant', stock__gt=0).count())
        selling_out = sum(1 for t, s in plan if s == 0 and t.stock > 0)
        if (not force and selling_out >= self.MASS_SELLOUT_MIN
                and selling_out > self.MASS_SELLOUT_SHARE * max(in_stock, 1)):
            return Response({
                'error': f'This sync would mark {selling_out} of {in_stock} in-stock items as sold out. '
                         'Nothing was saved. Check the stock list, or send "force": true if it is correct.',
            }, status=status.HTTP_409_CONFLICT)

        changed = []
        with transaction.atomic():
            for target, stock in plan:
                old = target.stock
                if not dry_run:
                    target.stock = stock
                    target.save(update_fields=['stock'])
                is_model = isinstance(target, Product)
                changed.append({
                    'level': 'model' if is_model else 'configuration',
                    'id': None if is_model else target.id,
                    'product_sku': target.sku if is_model else target.product.sku,
                    'old': old, 'new': stock,
                })
        logging.getLogger('orders.services').info(
            f"[StockSync] dry_run={dry_run} changed={len(changed)} unchanged={unchanged} "
            f"not_found={len(not_found)} errors={len(errors)}"
        )
        return Response({
            'dry_run': dry_run,
            'changed': changed,
            'unchanged': unchanged,
            'not_found': not_found,
            'errors': errors,
        })


class StockSyncOrdersView(APIView):
    """
    Website orders for the shop's stock app, so online sales and cancellations
    get recorded there before the next stock push. Read-only.

    GET /api/store/stock-sync/orders/?since=<ISO datetime>
    Header: X-Stock-Sync-Token

    Returns orders changed after `since` (oldest first, max 200) that took stock
    (payment_status Paid / Deposit Paid) or are Cancelled, plus `next_since`
    to pass on the next call.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    LIMIT = 200

    def get(self, request):
        from datetime import timezone as dt_timezone
        from django.utils.dateparse import parse_datetime
        from orders.models import Order

        denied = _stock_sync_denied(request)
        if denied:
            return denied

        raw = request.query_params.get('since', '')
        since = parse_datetime(raw) if raw else None
        if raw and since is None:
            return Response({'error': '"since" must be an ISO date-time'}, status=status.HTTP_400_BAD_REQUEST)
        if since is not None and timezone.is_naive(since):
            since = timezone.make_aware(since, dt_timezone.utc)

        qs = Order.objects.filter(
            Q(payment_status__in=['Paid', 'Deposit Paid']) | Q(order_status='Cancelled')
        )
        if since is not None:
            qs = qs.filter(updated_at__gt=since)
        orders = list(qs.order_by('updated_at', 'id').prefetch_related('items__variant__product')[:self.LIMIT])

        data = []
        for o in orders:
            data.append({
                'id': o.id,
                'created_at': o.created_at.isoformat(),
                'updated_at': o.updated_at.isoformat(),
                'order_status': o.order_status,
                'payment_status': o.payment_status,
                'payment_method': o.payment_method,
                'name': f"{o.first_name} {o.last_name}".strip(),
                'phone': o.phone,
                'city': o.city,
                'total_amount': str(o.total_amount),
                'items': [{
                    'item_id': it.id,
                    'variant_id': it.variant_id,
                    'product_sku': it.variant.product.sku if it.variant and it.variant.product else '',
                    'product_name': it.product_name,
                    'variant_label': it.variant_label,
                    'quantity': it.quantity,
                    'price': str(it.price),
                    'serial_number': it.serial_number,
                } for it in o.items.all()],
            })
        return Response({
            'orders': data,
            'next_since': orders[-1].updated_at.isoformat() if orders else (since.isoformat() if since else timezone.now().isoformat()),
            'more': len(orders) == self.LIMIT,
        })


class WarrantyPlansView(APIView):
    """All warranty plans, for the warranty policy page. Terms come from /store/config/."""
    permission_classes = [AllowAny]

    def get(self, request):
        from .models import WarrantyPlan
        from .warranty import plan_data
        return Response([plan_data(p) for p in WarrantyPlan.objects.all()])
