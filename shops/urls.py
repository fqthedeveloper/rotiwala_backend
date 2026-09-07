from django.urls import path

from .views import (
    PublicShopListView,
    ShopListCreateView,
    ShopDetailView,
    AssignManagerView,
    RemoveManagerView,
    MyShopView,
    ManagerListView,
    NearbyShopView,
    OnlineOrderStatusView, ManagerOrderCapacityView,
    PauseOnlineOrdersView, ResumeOnlineOrdersView,
)

urlpatterns = [

    path("online-order-status/", OnlineOrderStatusView.as_view()),
    path("manager/settings/order-capacity/", ManagerOrderCapacityView.as_view()),
    path("manager/settings/order-capacity/pause/", PauseOnlineOrdersView.as_view()),
    path("manager/settings/order-capacity/resume/", ResumeOnlineOrdersView.as_view()),

    # ==========================
    # PUBLIC
    # ==========================

    path(
        "public/",
        PublicShopListView.as_view()
    ),

    path(
        "nearby/",
        NearbyShopView.as_view()
    ),

    # ==========================
    # ADMIN
    # ==========================

    path(
        "",
        ShopListCreateView.as_view()
    ),

    path(
        "<int:pk>/",
        ShopDetailView.as_view()
    ),

    path(
        "assign-manager/",
        AssignManagerView.as_view()
    ),

    path(
        "remove-manager/",
        RemoveManagerView.as_view()
    ),

    path(
        "my-shop/",
        MyShopView.as_view()
    ),

    path(
        "managers/",
        ManagerListView.as_view()
    ),
]