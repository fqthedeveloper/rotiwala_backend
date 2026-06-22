from django.urls import path

from .views import (
    CartView,
    AddToCartView,
    UpdateCartItemView,
    RemoveCartItemView,
    ClearCartView,
    CartCountView
)

urlpatterns = [

    path(
        "",
        CartView.as_view(),
        name="cart"
    ),

    path(
        "add/",
        AddToCartView.as_view(),
        name="cart-add"
    ),

    path(
        "update/<int:pk>/",
        UpdateCartItemView.as_view(),
        name="cart-update"
    ),

    path(
        "remove/<int:pk>/",
        RemoveCartItemView.as_view(),
        name="cart-remove"
    ),

    path(
        "clear/",
        ClearCartView.as_view(),
        name="cart-clear"
    ),
    
    path(
        "count/",
        CartCountView.as_view(),
        name="cart-count"
    ),
]