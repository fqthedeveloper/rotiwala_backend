from datetime import datetime, time, timedelta

from django.db.models import Q
from django.utils import timezone

from orders.models import Order


ACTIVE_ONLINE_ORDER_STATUSES = ("pending", "accepted", "preparing", "ready")


class OnlineOrderingUnavailable(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def get_business_date(value=None):
    local_value = timezone.localtime(value or timezone.now())
    if local_value.hour < 3:
        return local_value.date() - timedelta(days=1)
    return local_value.date()


def get_active_online_orders(shop, capacity_date=None):
    capacity_date = capacity_date or get_business_date()
    business_start = timezone.make_aware(datetime.combine(capacity_date, time(3)))
    business_end = business_start + timedelta(days=1)
    return Order.objects.filter(
        shop=shop,
        order_type="online",
        status__in=ACTIVE_ONLINE_ORDER_STATUSES,
    ).filter(
        Q(
            pickup_type="scheduled",
            pickup_time__gte=timezone.make_aware(datetime.combine(capacity_date, time.min)),
            pickup_time__lt=timezone.make_aware(datetime.combine(capacity_date + timedelta(days=1), time.min)),
        )
        | Q(
            pickup_type="instant",
            ordered_at__gte=business_start,
            ordered_at__lt=business_end,
        )
    )


def get_order_capacity_snapshot(shop, capacity_date=None):
    capacity_date = capacity_date or get_business_date()
    active_orders = get_active_online_orders(shop, capacity_date).count()
    maximum_orders = shop.max_online_orders
    capacity_reached = active_orders >= maximum_orders
    manually_paused = shop.online_orders_manually_paused
    return {
        "max_online_orders": maximum_orders,
        "capacity_date": capacity_date.isoformat(),
        "active_online_orders": active_orders,
        "available_capacity": max(maximum_orders - active_orders, 0),
        "manually_paused": manually_paused,
        "capacity_reached": capacity_reached,
        "accepting_online_orders": not manually_paused and not capacity_reached,
        "reason": (
            "MANUALLY_PAUSED" if manually_paused else
            "CAPACITY_REACHED" if capacity_reached else None
        ),
    }


def ensure_online_order_capacity(shop, capacity_date=None):
    snapshot = get_order_capacity_snapshot(shop, capacity_date)
    if snapshot["manually_paused"]:
        raise OnlineOrderingUnavailable(
            "ONLINE_ORDERING_PAUSED",
            "Online ordering is temporarily paused.",
        )
    if snapshot["capacity_reached"]:
        raise OnlineOrderingUnavailable(
            "ONLINE_ORDER_CAPACITY_REACHED",
            "Online ordering is temporarily unavailable because the restaurant is currently at full order capacity.",
        )
    return snapshot