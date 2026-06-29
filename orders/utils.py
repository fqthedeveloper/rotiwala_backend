from django.utils import timezone

from .models import Order, WalkInCart

def generate_online_order_number(shop):

    today = timezone.localdate()

    prefix = today.strftime("%m%d")

    last = (
        Order.objects.filter(
            shop=shop,
            order_type="online",
            ordered_at__date=today,
        )
        .order_by("-id")
        .first()
    )

    number = 1

    if last:
        try:
            number = int(last.order_number.split("-")[-1]) + 1
        except Exception:
            pass

    return f"{shop.shop_code}-O-{prefix}-{number:05d}"
    


def generate_walkin_order_number(shop):

    today = timezone.localdate()

    prefix = today.strftime("%m%d")

    last = (
        Order.objects.filter(
            shop=shop,
            order_type="walkin",
            ordered_at__date=today,
        )
        .order_by("-id")
        .first()
    )

    number = 1

    if last:
        try:
            number = int(last.order_number.split("-")[-1]) + 1
        except Exception:
            pass

    return f"{shop.shop_code}-WO-{prefix}-{number:05d}"


def generate_walkin_cart_number(shop):

    today = timezone.localdate()

    prefix = today.strftime("%m%d")

    last = (
        WalkInCart.objects.filter(
            shop=shop,
            created_at__date=today,
        )
        .order_by("-id")
        .first()
    )

    number = 1

    if last:
        try:
            number = int(last.cart_number.split("-")[-1]) + 1
        except Exception:
            pass

    return f"{shop.shop_code}-W-{prefix}-{number:05d}"