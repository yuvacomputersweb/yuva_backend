from django.urls import path
from .views import (
    HomePageContentView, CompanyPageContentView,
    BulkOrderPageContentView, StoresPageContentView,
    ContactPageContentView,BlogListView, BlogDetailView,
)

urlpatterns = [
    path('home/', HomePageContentView.as_view(), name='home-content'),
    path('company/', CompanyPageContentView.as_view(), name='company-content'),
    path('bulk-orders/', BulkOrderPageContentView.as_view(), name='bulk-content'),
    path('stores/', StoresPageContentView.as_view(), name='stores-content'),
    path('contact/', ContactPageContentView.as_view(), name='contact-content'),
    path('blogs/', BlogListView.as_view(), name='blog-list'),
    path('blogs/<slug:slug>/', BlogDetailView.as_view(), name='blog-detail'),
]
