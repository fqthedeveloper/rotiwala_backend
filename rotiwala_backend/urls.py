from django.contrib import admin
from django.urls import path
from django.urls import include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)
from shops.views import (
    OnlineOrderStatusView,
    ManagerOrderCapacityView,
    PauseOnlineOrdersView,
    ResumeOnlineOrdersView,
)

urlpatterns = [

    path("api/shop/online-order-status/", OnlineOrderStatusView.as_view()),
    path("api/manager/settings/order-capacity/", ManagerOrderCapacityView.as_view()),
    path("api/manager/settings/order-capacity/pause/", PauseOnlineOrdersView.as_view()),
    path("api/manager/settings/order-capacity/resume/", ResumeOnlineOrdersView.as_view()),

    path(
        "api/token/refresh/",
        TokenRefreshView.as_view()
    ),

    path(
        "admin/",
        admin.site.urls
    ),

    path(
        "api/accounts/",
        include("accounts.urls")
    ),

    path(
        "api/shops/",
        include("shops.urls")
    ),

    path(
        "api/menu/",
        include("menu.urls")
    ),

    path(
        "api/cart/",
        include("cart.urls")
    ),
    path(
        "api/orders/",
        include("orders.urls")
    ),
    path(
        "api/expenses/",
        include("expenses.urls")
    ),

    path(
        "api/reports/",
        include("reports.urls")
    ),

    path(
        "api/contact/",
        include("contact.urls")
    ),

    path(
        "api/discounts/",
        include("discounts.urls")
    ),

    path(
        "api/coupons/",
        include(
            "discounts.coupon_urls"
        )
    ),
    path('api/whatsapp/', include('whatsapp.urls')),
    path('api/videos/', include('videos.urls')),
    path('api/delivery/', include('delivery.urls')),

    ]

urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )