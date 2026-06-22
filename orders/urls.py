from django.urls import path

from .views import *

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
        "walkin/",
        WalkInOrderView.as_view()
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

]