from django.utils import timezone

from .models import (
    Order,
    WalkInCart,
)


def generate_order_number():

    today = timezone.localdate()

    prefix = today.strftime(
        "RT-O-%m%d"
    )

    count = (
        Order.objects.filter(
            ordered_at__date=today
        ).count()
        + 1
    )

    return (
        f"{prefix}-{count:05d}"
    )


def generate_walkin_cart_number():

    today = timezone.localdate()

    prefix = today.strftime(
        "RT-W-%m%d"
    )

    count = (
        WalkInCart.objects.filter(
            created_at__date=today
        ).count()
        + 1
    )

    return (
        f"{prefix}-{count:05d}"
    )