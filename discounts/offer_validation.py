from .models import DiscountUsage
from .coupon_models import CouponUsage


def customer_used_discount(
    customer,
    discount
):

    if customer is None:
        return False

    return DiscountUsage.objects.filter(
        customer=customer,
        discount=discount
    ).exists()


def customer_used_coupon(
    customer,
    coupon
):

    if customer is None:
        return False

    return CouponUsage.objects.filter(
        customer=customer,
        coupon=coupon
    ).exists()