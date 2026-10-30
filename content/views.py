from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from .models import (
    HeroSlide, SiteStat, HomeReview, PartnerBrand, AboutContent,
    CompanyContent, CompanyTimeline, CompanyInvestor,
    CompanyCertification, CompanyPartner,
    BulkOrderContent, BulkOrderBenefit, BulkScalePoint, BulkInventoryItem,
    StoreLocation, StoresPageContent,
    ContactPageContent, ContactDepartment,Blog
)
from .serializers import (
    HeroSlideSerializer, SiteStatSerializer, HomeReviewSerializer,
    PartnerBrandSerializer, AboutContentSerializer,
    CompanyContentSerializer, CompanyTimelineSerializer,
    CompanyInvestorSerializer, CompanyCertificationSerializer, CompanyPartnerSerializer,
    BulkOrderContentSerializer, BulkOrderBenefitSerializer,
    BulkScalePointSerializer, BulkInventoryItemSerializer,
    StoreLocationSerializer, StoresPageContentSerializer,
    ContactPageContentSerializer, ContactDepartmentSerializer,BlogListSerializer,BlogDetailSerializer,
)
from rest_framework import generics
from django.shortcuts import get_object_or_404


def _first(model):
    return model.objects.first()


class HomePageContentView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        slides = HeroSlide.objects.filter(is_active=True)
        stats = SiteStat.objects.all()
        reviews = HomeReview.objects.filter(is_active=True)
        partners = PartnerBrand.objects.filter(is_active=True)
        about = _first(AboutContent)

        return Response({
            'hero_slides': HeroSlideSerializer(slides, many=True, context={'request': request}).data,
            'stats': SiteStatSerializer(stats, many=True).data,
            'reviews': HomeReviewSerializer(reviews, many=True).data,
            'partners': PartnerBrandSerializer(partners, many=True).data,
            'about': AboutContentSerializer(about, context={'request': request}).data if about else None,
        })


class CompanyPageContentView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        content = _first(CompanyContent)
        timeline = CompanyTimeline.objects.all()
        investors = CompanyInvestor.objects.filter(is_active=True)
        certifications = CompanyCertification.objects.filter(is_active=True)
        partners = CompanyPartner.objects.filter(is_active=True)

        return Response({
            'content': CompanyContentSerializer(content, context={'request': request}).data if content else None,
            'timeline': CompanyTimelineSerializer(timeline, many=True).data,
            'investors': CompanyInvestorSerializer(investors, many=True).data,
            'certifications': CompanyCertificationSerializer(certifications, many=True).data,
            'partners': CompanyPartnerSerializer(partners, many=True).data,
        })


class BulkOrderPageContentView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        content = _first(BulkOrderContent)
        benefits = BulkOrderBenefit.objects.all()
        scale_points = BulkScalePoint.objects.filter(is_active=True)
        inventory = BulkInventoryItem.objects.all()

        return Response({
            'content': BulkOrderContentSerializer(content, context={'request': request}).data if content else None,
            'benefits': BulkOrderBenefitSerializer(benefits, many=True).data,
            'scale_points': BulkScalePointSerializer(scale_points, many=True).data,
            'inventory': BulkInventoryItemSerializer(inventory, many=True).data,
        })


class StoresPageContentView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        content = _first(StoresPageContent)
        stores = StoreLocation.objects.filter(is_active=True)

        return Response({
            'content': StoresPageContentSerializer(content).data if content else None,
            'stores': StoreLocationSerializer(stores, many=True).data,
        })


class ContactPageContentView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        content = _first(ContactPageContent)
        departments = ContactDepartment.objects.filter(is_active=True)

        return Response({
            'content': ContactPageContentSerializer(content).data if content else None,
            'departments': ContactDepartmentSerializer(departments, many=True).data,
        })

class BlogListView(generics.ListAPIView):
    serializer_class = BlogListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Blog.objects.filter(is_published=True)
        limit = self.request.query_params.get('limit')
        if limit:
            try:
                qs = qs[:int(limit)]
            except ValueError:
                pass
        return qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        serializer = BlogListSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class BlogDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        blog = get_object_or_404(Blog, slug=slug, is_published=True)
        return Response(BlogDetailSerializer(blog, context={'request': request}).data)
