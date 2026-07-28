from django.urls import path
from django.http import HttpResponse
from .views import *

urlpatterns = [
    # Root path for orders (optional, can return a message or redirect)
    path('', lambda request: HttpResponse('Orders API root'), name='orders-root'),
    
    # Customer endpoints
    path('place/', PlaceOrderView.as_view(), name='place-order'),
    path('my-orders/', MyOrdersView.as_view(), name='my-orders'),
    path('<int:pk>/', OrderDetailView.as_view(), name='order-detail'),
    path('<int:pk>/cancel/', CancelOrderView.as_view(), name='cancel-order'),
    
    # Manager endpoints
    path('manager/', ManagerOrdersView.as_view(), name='manager-orders'),
    path('dashboard/', ManagerDashboardView.as_view(), name='manager-dashboard'),
    
    # Order status updates
    path('<int:pk>/accept/', AcceptOrderView.as_view(), name='accept-order'),
    path('<int:pk>/reject/', RejectOrderView.as_view(), name='reject-order'),
    path('<int:pk>/preparing/', PreparingOrderView.as_view(), name='preparing-order'),
    path('<int:pk>/ready/', ReadyOrderView.as_view(), name='ready-order'),
    path('<int:pk>/collected/', CollectedOrderView.as_view(), name='collected-order'),
    path('<int:pk>/payment/', PaymentReceivedView.as_view(), name='payment-received'),
    
    # Promotions
    path('available-promotions/', AvailablePromotionsView.as_view(), name='available-promotions'),
    path('checkout/preview/', CheckoutPreviewView.as_view(), name='checkout-preview'),
    
    # Customer search
    path('customer-search/', CustomerSearchView.as_view(), name='customer-search'),
    
    # Walk-in cart endpoints
    path('walkin/cart/create/', CreateWalkInCartView.as_view(), name='create-walkin-cart'),
    path('walkin/cart/', WalkInCartListView.as_view(), name='walkin-cart-list'),
    path('walkin/cart/<int:pk>/', WalkInCartDetailView.as_view(), name='walkin-cart-detail'),
    path('walkin/cart/<int:pk>/add-item/', AddWalkInCartItemView.as_view(), name='add-walkin-cart-item'),
    path('walkin/cart/item/<int:pk>/', UpdateWalkInCartItemView.as_view(), name='update-walkin-cart-item'),
    path('walkin/cart/item/<int:pk>/delete/', DeleteWalkInCartItemView.as_view(), name='delete-walkin-cart-item'),
    path('walkin/cart/<int:pk>/update/', UpdateWalkInCartView.as_view(), name='update-walkin-cart'),
    path('walkin/cart/<int:pk>/place/', PlaceWalkInCartView.as_view(), name='place-walkin-cart'),
    
    # Walk-in order management
    path('walkin/order/<int:pk>/update/', UpdatePlacedOrderView.as_view(), name='update-placed-order'),
    path('walkin/order/<int:pk>/add-item/', AddPlacedOrderItemView.as_view(), name='add-placed-order-item'),
    path('walkin/order/item/<int:pk>/', UpdatePlacedOrderItemView.as_view(), name='update-placed-order-item'),
    path('walkin/order/item/<int:pk>/delete/', DeletePlacedOrderItemView.as_view(), name='delete-placed-order-item'),
    
    # Receipt endpoints
    path('receipt/<int:pk>/', GenerateReceiptView.as_view(), name='generate-receipt'),
    path('receipt/<int:pk>/print/', PrintReceiptView.as_view(), name='print-receipt'),
    path('receipt/<int:pk>/download/pdf/', DownloadReceiptPDFView.as_view(), name='download-receipt-pdf'),
    path('receipt/<int:pk>/download/text/', DownloadReceiptTextView.as_view(), name='download-receipt-text'),
    path('receipt/bulk-print/', BulkPrintReceiptsView.as_view(), name='bulk-print-receipts'),
    path('receipt/bill-types/', AvailableBillTypesView.as_view(), name='bill-types'),
    path('receipt/<int:pk>/view/', ViewReceiptPDFView.as_view(), name='view-receipt-pdf'),
    path('superadmin/orders/', SuperAdminOrderListView.as_view(), name='superadmin-orders'),

]