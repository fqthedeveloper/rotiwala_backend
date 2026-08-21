# accounts/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter

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
    SendOTPView,
    TestWhatsAppView,
    VerifyOTPView,
    ChangePasswordView,
    SendPhoneUpdateOTPView,
    VerifyPhoneUpdateOTPView,
    SendPasswordResetOTPView,
    VerifyPasswordResetOTPView,
    # NEW:
    CustomerAddressViewSet,
)

# ============================================================
# Router for Customer Addresses
# ============================================================

router = DefaultRouter()
router.register(r'addresses', CustomerAddressViewSet, basename='customer-address')

# ============================================================
# URL Patterns
# ============================================================

urlpatterns = [
    # Authentication
    path("register/", CustomerRegisterView.as_view()),
    path("firebase-login/", FirebaseLoginView.as_view()),
    path("password-login/", PasswordLoginView.as_view()),
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('test-whatsapp/', TestWhatsAppView.as_view()),

    # FCM
    path("save-fcm-token/", SaveFCMTokenView.as_view()),

    # Manager management (super admin only)
    path("managers/", ManagerListView.as_view()),
    path("create-manager/", CreateManagerView.as_view()),
    path("assign-manager/", AssignManagerView.as_view()),
    path("managers/<int:pk>/", ManagerDetailView.as_view()),

    # Customer management
    path('customers/', CustomerListView.as_view(), name='customer-list'),
    path('customers/<int:pk>/', CustomerDetailView.as_view(), name='customer-detail'),
    path('profile/', CustomerSelfProfileView.as_view(), name='self-profile'),
    path('customers/<int:customer_id>/flag/', CustomerFlagCreateView.as_view(), name='customer-flag-create'),
    path('customers/<int:customer_id>/flag/<int:flag_id>/', CustomerFlagDeleteView.as_view(), name='customer-flag-delete'),
    path('customers/<int:customer_id>/toggle-block/', CustomerToggleBlockView.as_view(), name='customer-toggle-block'),

    # Super admin dashboard
    path('superadmin/dashboard/stats/', SuperAdminDashboardStatsView.as_view(), name='superadmin-stats'),
    path('superadmin/dashboard/recent_orders/', SuperAdminRecentOrdersView.as_view(), name='superadmin-recent-orders'),
    path('superadmin/dashboard/revenue_trend/', SuperAdminRevenueTrendView.as_view(), name='superadmin-revenue-trend'),
    path('superadmin/dashboard/orders_by_shop/', SuperAdminOrdersByShopView.as_view(), name='superadmin-orders-by-shop'),
    path('superadmin/dashboard/top_products/', SuperAdminTopProductsView.as_view(), name='superadmin-top-products'),

    # Password & phone update
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('send-phone-update-otp/', SendPhoneUpdateOTPView.as_view(), name='send-phone-update-otp'),
    path('verify-phone-update-otp/', VerifyPhoneUpdateOTPView.as_view(), name='verify-phone-update-otp'),

    # Password reset via OTP
    path('send-password-reset-otp/', SendPasswordResetOTPView.as_view(), name='send-password-reset-otp'),
    path('verify-password-reset-otp/', VerifyPasswordResetOTPView.as_view(), name='verify-password-reset-otp'),

    # ============================================================
    # NEW: Customer Delivery Address endpoints
    # ============================================================
    path('', include(router.urls)),
]