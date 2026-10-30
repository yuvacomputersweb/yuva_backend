from django.urls import path

from . import views

urlpatterns = [
    path('pincode/', views.PincodeCheckView.as_view(), name='pincode-check'),
    path('stock-alerts/', views.StockAlertView.as_view(), name='stock-alert'),
    path('cart/', views.CartSnapshotView.as_view(), name='cart-snapshot'),
    path('trade-in/', views.TradeInView.as_view(), name='trade-in'),
    path('warranty/', views.WarrantyLookupView.as_view(), name='warranty-lookup'),
    path('google-reviews/', views.GoogleReviewsView.as_view(), name='google-reviews'),
    path('offers/', views.OffersView.as_view(), name='offers'),
]
