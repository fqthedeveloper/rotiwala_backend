# orders/token_utils.py

from django.db import transaction
from delivery.models import WalkInTokenCounter, get_business_date


def assign_walkin_token(order):
    """
    Assign a short token to a walk-in order.
    Called AFTER the order is created.
    """
    if order.order_type != 'walkin':
        return None

    token = WalkInTokenCounter.get_next_token(order.shop)
    business_date = get_business_date()

    with transaction.atomic():
        order.token_number = token
        order.business_date = business_date
        order.save(update_fields=['token_number', 'business_date'])

    return token


def get_walkin_display_token(order):
    """
    Returns the short token for display, or None for online orders.
    """
    return order.token_number if order.order_type == 'walkin' else None


def get_display_screen_tokens(shop, business_date=None):
    """
    Returns live orders for the display screen (both walk-in and delivery):
    - preparing: orders being prepared / accepted
    - ready: orders ready for counter pickup or delivery rider pickup
    - out_for_delivery: delivery orders out with driver
    - recent_completed: last completed/collected/delivered orders
    """
    if business_date is None:
        business_date = get_business_date()

    from django.db.models import Q
    from orders.models import Order

    # Match business_date or ordered_at on business_date
    date_filter = Q(business_date=business_date) | Q(business_date__isnull=True, ordered_at__date=business_date)
    base_qs = Order.objects.filter(shop=shop).filter(date_filter)

    def format_order(o):
        is_delivery = (o.delivery_option == 'delivery' or o.order_type == 'online')
        if o.token_number:
            token_display = o.token_number
        else:
            short_num = o.order_number.replace("ORD-", "")[-4:] if o.order_number else str(o.id)
            token_display = f"D-{short_num}" if is_delivery else short_num

        driver_name = None
        driver_phone = None
        delivery_status = None
        if is_delivery:
            try:
                assignment = getattr(o, 'delivery_assignment', None)
                if assignment and assignment.delivery_boy:
                    driver_name = assignment.delivery_boy.full_name
                    driver_phone = assignment.delivery_boy.phone
                    delivery_status = assignment.status
            except Exception:
                pass

        cust_name = o.customer_name
        if not cust_name and o.customer:
            cust_name = o.customer.first_name or o.customer.username
        if not cust_name:
            cust_name = "Walk-in Customer" if not is_delivery else "Delivery Order"

        return {
            "order_id": o.id,
            "token_number": token_display,
            "order_number": o.order_number,
            "order_type": o.order_type,
            "delivery_option": o.delivery_option,
            "is_delivery": is_delivery,
            "type_label": "🛵 Delivery" if is_delivery else "🚶 Walk-In",
            "customer_name": cust_name,
            "driver_name": driver_name,
            "driver_phone": driver_phone,
            "delivery_status": delivery_status,
            "status": o.status,
            "ordered_at": o.ordered_at.isoformat() if o.ordered_at else None,
            "ready_at": o.ready_at.isoformat() if o.ready_at else None,
            "collected_at": o.collected_at.isoformat() if o.collected_at else None,
            "estimated_minutes": o.estimated_minutes,
        }

    preparing_qs = base_qs.filter(
        status__in=['pending', 'accepted', 'preparing']
    ).select_related('delivery_assignment__delivery_boy').order_by('ordered_at')

    ready_qs = base_qs.filter(
        status='ready'
    ).select_related('delivery_assignment__delivery_boy').order_by('ready_at')

    out_for_delivery_qs = base_qs.filter(
        delivery_option='delivery',
        delivery_assignment__status__in=['picked_up', 'out_for_delivery']
    ).select_related('delivery_assignment__delivery_boy').order_by('-ready_at', '-ordered_at')[:8]

    recent_completed_qs = base_qs.filter(
        status__in=['collected', 'delivered']
    ).select_related('delivery_assignment__delivery_boy').order_by('-collected_at', '-ordered_at')[:8]

    preparing_list = [format_order(o) for o in preparing_qs]
    ready_list = [format_order(o) for o in ready_qs]
    out_for_delivery_list = [format_order(o) for o in out_for_delivery_qs]
    recent_completed_list = [format_order(o) for o in recent_completed_qs]

    return {
        "shop_id": shop.id,
        "shop_name": shop.name,
        "shop_code": getattr(shop, 'shop_code', None),
        "business_date": str(business_date),
        "preparing": preparing_list,
        "ready": ready_list,
        "out_for_delivery": out_for_delivery_list,
        "recent_completed": recent_completed_list,
        "counts": {
            "total_preparing": len(preparing_list),
            "total_ready": len(ready_list),
            "total_out_for_delivery": len(out_for_delivery_list),
            "walkin_ready": sum(1 for o in ready_list if not o["is_delivery"]),
            "delivery_ready": sum(1 for o in ready_list if o["is_delivery"]),
        }
    }