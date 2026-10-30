from django.urls import path
from .views import (
    BrandListView, CategoryListView, UsageTagListView,
    ProductListView, ProductDetailView, ReviewListCreateView,
    HomeDataView, SiteConfigView, GlobalSearchView, ValidateCouponView,CategoryBrandListView
)

urlpatterns = [
    path('brands/', BrandListView.as_view(), name='brand-list'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('usage-tags/', UsageTagListView.as_view(), name='usage-tag-list'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<slug:slug>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/<slug:slug>/reviews/', ReviewListCreateView.as_view(), name='product-reviews'),
    path('home-data/', HomeDataView.as_view(), name='home-data'),
    path('config/', SiteConfigView.as_view(), name='site-config'),
    path('search/', GlobalSearchView.as_view(), name='search'),
    path('validate-coupon/', ValidateCouponView.as_view(), name='validate-coupon'),
    path('categories/<slug:slug>/brands/', CategoryBrandListView.as_view(), name='category-brands'),
]