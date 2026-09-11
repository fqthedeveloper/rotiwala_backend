from asgiref.sync import (
    async_to_sync
)

from channels.layers import (
    get_channel_layer
)
from shops.services import get_order_capacity_snapshot


def send_order_update(
    order
):

    channel_layer = (
        get_channel_layer()
    )

    if not channel_layer:
        return

    capacity = get_order_capacity_snapshot(order.shop)

    is_delivery = bool(order.delivery_option == 'delivery' or order.order_type == 'online')
    driver_name = None
    delivery_status = None
    if is_delivery:
        try:
            assignment = order.delivery_assignments.filter(
                status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery', 'delivered']
            ).select_related('delivery_boy').first()
            if assignment and assignment.delivery_boy:
                driver_name = assignment.delivery_boy.full_name
                delivery_status = assignment.status
        except Exception:
            pass

    token_display = order.token_number
    if not token_display:
        short_num = order.order_number.replace("ORD-", "")[-4:] if order.order_number else str(order.id)
        token_display = f"D-{short_num}" if is_delivery else short_num

    payload = {
        "type": "order_update",
        "order_id": order.id,
        "order_number": order.order_number,
        "order_type": order.order_type,
        "delivery_option": order.delivery_option,
        "is_delivery": is_delivery,
        "token_number": token_display,
        "driver_name": driver_name,
        "delivery_status": delivery_status,
        "customer_name": order.customer_name or (order.customer.first_name if order.customer else "") or ("Customer" if not is_delivery else "Delivery"),
        "business_date": str(order.business_date) if order.business_date else None,
        "status": order.status,
        "payment_status": order.payment_status,
        "capacity": capacity,
        "shop_id": order.shop.id if order.shop else None,
    }

    # 1. To customer tracking order
    async_to_sync(
        channel_layer.group_send
    )(
        f"order_{order.id}",
        {
            "type": "order_update",
            "data": payload
        }
    )

    # 2. To manager & kitchen general group
    async_to_sync(
        channel_layer.group_send
    )(
        "manager_orders",
        {
            "type": "manager_order_update",
            "data": payload
        }
    )

    # 3. To shop-specific staff (manager + preparing staff)
    if order.shop:
        async_to_sync(
            channel_layer.group_send
        )(
            f"shop_{order.shop.id}_staff",
            {
                "type": "staff_order_update",
                "data": payload
            }
        )

        # 4. To shop-specific TV display screen
        async_to_sync(
            channel_layer.group_send
        )(
            f"shop_{order.shop.id}_display",
            {
                "type": "display_update",
                "data": payload
            }
        )


def send_new_order(
    order
):

    channel_layer = (
        get_channel_layer()
    )

    if not channel_layer:
        return

    capacity = get_order_capacity_snapshot(order.shop)

    is_delivery = bool(order.delivery_option == 'delivery' or order.order_type == 'online')
    token_display = order.token_number
    if not token_display:
        short_num = order.order_number.replace("ORD-", "")[-4:] if order.order_number else str(order.id)
        token_display = f"D-{short_num}" if is_delivery else short_num

    payload = {
        "type": "new_order",
        "order_id": order.id,
        "order_number": order.order_number,
        "order_type": order.order_type,
        "delivery_option": order.delivery_option,
        "is_delivery": is_delivery,
        "token_number": token_display,
        "customer_name": order.customer_name or (order.customer.first_name if order.customer else "") or ("Customer" if not is_delivery else "Delivery"),
        "business_date": str(order.business_date) if order.business_date else None,
        "status": order.status,
        "payment_status": order.payment_status,
        "capacity": capacity,
        "shop_id": order.shop.id if order.shop else None,
    }

    async_to_sync(
        channel_layer.group_send
    )(
        "manager_orders",
        {
            "type": "manager_order_update",
            "data": payload
        }
    )

    if order.shop:
        async_to_sync(
            channel_layer.group_send
        )(
            f"shop_{order.shop.id}_staff",
            {
                "type": "staff_order_update",
                "data": payload
            }
        )
        async_to_sync(
            channel_layer.group_send
        )(
            f"shop_{order.shop.id}_display",
            {
                "type": "display_update",
                "data": payload
            }
        )


def broadcast_display_update(shop):
    """Broadcasts a full display screen refresh event for the given shop."""
    channel_layer = get_channel_layer()
    if not channel_layer or not shop:
        return

    from orders.token_utils import get_display_screen_tokens
    tokens_data = get_display_screen_tokens(shop)

    async_to_sync(
        channel_layer.group_send
    )(
        f"shop_{shop.id}_display",
        {
            "type": "display_refresh",
            "data": tokens_data
        }
    )