from django.urls import path

from .views import (
    FirebaseLoginView,
    CustomerRegisterView,
    SaveFCMTokenView,
    PasswordLoginView,
    CreateManagerView,
    ManagerListView,
    AssignManagerView,
    ManagerDetailView,
    CustomerListView,
    CustomerDetailView,
    CustomerFlagCreateView,
    CustomerFlagDeleteView,
    CustomerToggleBlockView,
    CustomerSelfProfileView,
    SuperAdminDashboardStatsView,
    SuperAdminRecentOrdersView,
    SuperAdminRevenueTrendView,
    SuperAdminOrdersByShopView,
    SuperAdminTopProductsView,
    
)

urlpatterns = [

    path(
        "register/",
        CustomerRegisterView.as_view()
    ),

    path(
        "firebase-login/",
        FirebaseLoginView.as_view()
    ),

    path(
        "password-login/",
        PasswordLoginView.as_view()
    ),


    path(
        "save-fcm-token/",
        SaveFCMTokenView.as_view()
    ),
        path(
        "managers/",
        ManagerListView.as_view()
    ),

    path(
        "create-manager/",
        CreateManagerView.as_view()
    ),
    path(
        "assign-manager/",
        AssignManagerView.as_view()
    ),
    
    path(
        "managers/<int:pk>/",
        ManagerDetailView.as_view()
    ),
    
    path('customers/', CustomerListView.as_view(), name='customer-list'),
    path('customers/<int:pk>/', CustomerDetailView.as_view(), name='customer-detail'),
    path('profile/', CustomerSelfProfileView.as_view(), name='self-profile'),  # new
    path('customers/<int:customer_id>/flag/', CustomerFlagCreateView.as_view(), name='customer-flag-create'),
    path('customers/<int:customer_id>/flag/<int:flag_id>/', CustomerFlagDeleteView.as_view(), name='customer-flag-delete'),
    path('customers/<int:customer_id>/toggle-block/', CustomerToggleBlockView.as_view(), name='customer-toggle-block'),
    path('superadmin/dashboard/stats/', SuperAdminDashboardStatsView.as_view(), name='superadmin-stats'),
    path('superadmin/dashboard/recent_orders/', SuperAdminRecentOrdersView.as_view(), name='superadmin-recent-orders'),
    path('superadmin/dashboard/revenue_trend/', SuperAdminRevenueTrendView.as_view(), name='superadmin-revenue-trend'),
    path('superadmin/dashboard/orders_by_shop/', SuperAdminOrdersByShopView.as_view(), name='superadmin-orders-by-shop'),
    path('superadmin/dashboard/top_products/', SuperAdminTopProductsView.as_view(), name='superadmin-top-products'),

]