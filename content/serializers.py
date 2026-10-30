from rest_framework import serializers
from .models import (
    HeroSlide, SiteStat, HomeReview, PartnerBrand, AboutContent,
    CompanyContent, CompanyTimeline, CompanyInvestor,
    CompanyCertification, CompanyPartner,
    BulkOrderContent, BulkOrderBenefit, BulkScalePoint, BulkInventoryItem,
    StoreLocation, StoresPageContent,
    ContactPageContent, ContactDepartment,Blog
)


class HeroSlideSerializer(serializers.ModelSerializer):
    class Meta:
        model = HeroSlide
        fields = ['id', 'image', 'order']


class SiteStatSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteStat
        fields = ['label', 'value', 'order']


class HomeReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeReview
        fields = ['id', 'name', 'rating', 'text']


class PartnerBrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = PartnerBrand
        fields = ['id', 'name', 'color', 'order']


class AboutContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = AboutContent
        fields = '__all__'


class CompanyTimelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyTimeline
        fields = ['year', 'title', 'description', 'order']


class CompanyInvestorSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyInvestor
        fields = ['name', 'type', 'order']


class CompanyCertificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyCertification
        fields = ['name', 'order']


class CompanyPartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyPartner
        fields = ['name', 'order']


class CompanyContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyContent
        fields = '__all__'


class BulkOrderBenefitSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkOrderBenefit
        fields = ['title', 'description', 'icon', 'order']


class BulkScalePointSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkScalePoint
        fields = ['text', 'order']


class BulkInventoryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkInventoryItem
        fields = ['device_type', 'units_available', 'order']


class BulkOrderContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BulkOrderContent
        fields = '__all__'


class StoreLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreLocation
        fields = ['id', 'name', 'state', 'phone', 'maps_url', 'address', 'order']


class StoresPageContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoresPageContent
        fields = '__all__'


class ContactDepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactDepartment
        fields = ['label', 'number', 'icon', 'order']


class ContactPageContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactPageContent
        fields = '__all__'

from .models import Blog  # add to existing import

class BlogListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = ['id', 'title', 'slug', 'cover_image', 'excerpt', 'created_at']

class BlogDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Blog
        fields = ['id', 'title', 'slug', 'cover_image', 'excerpt', 'paragraphs', 'created_at', 'updated_at']
