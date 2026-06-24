from django.urls import (
    re_path
)

from .consumers import (
    OrderConsumer,
    ManagerOrderConsumer
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

]