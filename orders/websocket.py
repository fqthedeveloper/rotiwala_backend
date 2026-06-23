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

                "order_id": order.id,

                "status": order.status,

                "payment_status":
                order.payment_status,

                "order_number":
                order.order_number

            },
        },
    )
    

