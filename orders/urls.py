from django.urls import path
from .views import (
    CheckoutView, OrderListView, order_detail,
    ReturnRequestCreateView, ValidateExchangeCodeView, CancelOrderView
)

urlpatterns = [
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('', OrderListView.as_view(), name='order-list'),
    path('<int:pk>/', order_detail, name='order-detail'),
    path('<int:pk>/cancel/', CancelOrderView.as_view(), name='cancel-order'),
    path('<int:order_id>/return/', ReturnRequestCreateView.as_view(), name='return-request'),
    path('validate-exchange-code/', ValidateExchangeCodeView.as_view(), name='validate-exchange'),
]