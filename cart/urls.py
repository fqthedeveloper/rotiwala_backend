from django.urls import path

from .views import CartView
from .views import AddToCartView
from .views import RemoveCartItemView

urlpatterns = [

    path(
        "",
        CartView.as_view()
    ),

    path(
        "add/",
        AddToCartView.as_view()
    ),

    path(
        "remove/<int:pk>/",
        RemoveCartItemView.as_view()
    ),

]