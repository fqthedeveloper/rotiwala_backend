from asgiref.sync import (
    async_to_sync
)

from channels.layers import (
    get_channel_layer
)


def send_order_update(
    order
):

    channel_layer = (
        get_channel_layer()
    )

    async_to_sync(
        channel_layer.group_send
    )(
        f"order_{order.id}",
        {
            "type": "order_update",
            "data": {
                "type": "order_update",
                "order_id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "payment_status": order.payment_status,
            }
        }
    )

    async_to_sync(
        channel_layer.group_send
    )(
        "manager_orders",
        {
            "type": "manager_order_update",
            "data": {
                "type": "order_update",
                "order_id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "payment_status": order.payment_status,
            }
        }
    )


def send_new_order(
    order
):

    channel_layer = (
        get_channel_layer()
    )

    async_to_sync(
        channel_layer.group_send
    )(
        "manager_orders",
        {
            "type": "manager_order_update",
            "data": {
                "type": "new_order",
                "order_id": order.id,
                "order_number": order.order_number,
                "status": order.status,
                "payment_status": order.payment_status,
            }
        }
    )