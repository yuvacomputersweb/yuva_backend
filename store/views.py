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
