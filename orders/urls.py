from django.urls import path

from .views import *

from .views import (
    GenerateReceiptView,
    PrintReceiptView,
    BulkPrintReceiptsView
)


urlpatterns = [

    path(
        "place/",
        PlaceOrderView.as_view()
    ),

    path(
        "my-orders/",
        MyOrdersView.as_view()
    ),

    path(
        "manager/",
        ManagerOrdersView.as_view()
    ),

    path(
        "<int:pk>/accept/",
        AcceptOrderView.as_view()
    ),

    path(
        "<int:pk>/reject/",
        RejectOrderView.as_view()
    ),

    path(
        "<int:pk>/preparing/",
        PreparingOrderView.as_view()
    ),

    path(
        "<int:pk>/ready/",
        ReadyOrderView.as_view()
    ),

    path(
        "<int:pk>/collected/",
        CollectedOrderView.as_view()
    ),
    
    path(
        "<int:pk>/cancel/",
        CancelOrderView.as_view()
    ),
    
    path('available-promotions/', AvailablePromotionsView.as_view(), name='available-promotions'),

    path('checkout/preview/', CheckoutPreviewView.as_view(), name='checkout-preview'),
        
    path(
        "dashboard/",
        ManagerDashboardView.as_view()
    ),

    path(
        "<int:pk>/",
        OrderDetailView.as_view()
    ),

    path(
        "<int:pk>/payment/",
        PaymentReceivedView.as_view()
    ),
    
    
    
    path(
        "customer-search/",
        CustomerSearchView.as_view()
    ),
    
    path(
        "walkin/cart/create/",
        CreateWalkInCartView.as_view()
    ),

    path(
        "walkin/cart/",
        WalkInCartListView.as_view()
    ),

    path(
        "walkin/cart/<int:pk>/",
        WalkInCartDetailView.as_view()
    ),
    
    path(
        "walkin/cart/<int:pk>/add-item/",
        AddWalkInCartItemView.as_view()
    ),

    path(
        "walkin/cart/item/<int:pk>/",
        UpdateWalkInCartItemView.as_view()
    ),

    path(
        "walkin/cart/item/<int:pk>/delete/",
        DeleteWalkInCartItemView.as_view()
    ),
    
    path(
        "walkin/cart/<int:pk>/update/",
        UpdateWalkInCartView.as_view()
    ),

    path(
        "walkin/cart/<int:pk>/place/",
        PlaceWalkInCartView.as_view()
    ),
    
    path(
        "walkin/order/<int:pk>/update/",
        UpdatePlacedOrderView.as_view()
    ),
    
    path(
        "walkin/order/<int:pk>/add-item/",
        AddPlacedOrderItemView.as_view()
    ),
    
    path(
        "walkin/order/item/<int:pk>/",
        UpdatePlacedOrderItemView.as_view()
    ),
    
    path(
        "walkin/order/item/<int:pk>/delete/",
        DeletePlacedOrderItemView.as_view()
    ),
    
    path('receipt/<int:pk>/', GenerateReceiptView.as_view(), name='generate-receipt'),
    path('receipt/<int:pk>/print/', PrintReceiptView.as_view(), name='print-receipt'),
    path('receipt/bulk-print/', BulkPrintReceiptsView.as_view(), name='bulk-print-receipts'),
]