from django.utils import timezone

from .models import Order


def generate_order_number():

    today = timezone.localdate()

    prefix = today.strftime(
        "RT-%m%d"
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