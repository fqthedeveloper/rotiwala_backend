from django.urls import (
    re_path
)

from .consumers import (
    OrderConsumer,
    ManagerOrderConsumer,
    StaffOrderConsumer,
    DisplayScreenConsumer,
)

websocket_urlpatterns = [

    re_path(
        r"ws/orders/(?P<order_id>\d+)/$",
        OrderConsumer.as_asgi(),
    ),

    re_path(
        r"ws/manager/orders/$",
        ManagerOrderConsumer.as_asgi(),
    ),

    re_path(
        r"ws/staff/orders/(?P<shop_id>\d+)/$",
        StaffOrderConsumer.as_asgi(),
    ),

    re_path(
        r"ws/display/(?P<shop_id>\d+)/$",
        DisplayScreenConsumer.as_asgi(),
    ),

]