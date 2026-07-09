from django.urls import path

from .coupon_views import *

urlpatterns=[

    path(
        "",
        CouponListCreateView.as_view()
    ),

    path(
        "dashboard/",
        CouponDashboardView.as_view()
    ),

    path(
        "bulk/",
        BulkCouponGeneratorView.as_view()
    ),

    path(
        "<int:pk>/",
        CouponDetailView.as_view()
    ),

]