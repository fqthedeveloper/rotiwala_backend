from django.utils import timezone

from .coupon_models import (
    Coupon,
    CouponUsage,
)


def validate_coupon(
    coupon,
    customer,
    order_amount,
):

    now = timezone.now()

    if coupon.status != "active":

        return (
            False,
            "Coupon inactive."
        )

    if now < coupon.start_date:

        return (
            False,
            "Coupon not started."
        )

    if now > coupon.end_date:

        return (
            False,
            "Coupon expired."
        )

    if (
        order_amount <
        coupon.minimum_order_amount
    ):

        return (
            False,
            (
                f"Minimum order "
                f"₹{coupon.minimum_order_amount}"
            )
        )

    if (
        coupon.usage_limit > 0
        and
        coupon.used_count >=
        coupon.usage_limit
    ):

        return (
            False,
            "Coupon exhausted."
        )

    customer_usage = CouponUsage.objects.filter(

        coupon=coupon,

        customer=customer

    ).count()

    if (
        customer_usage >=
        coupon.per_customer_limit
    ):

        return (
            False,
            "Coupon already used."
        )

    if coupon.first_order_only:

        if customer.orders.count() > 0:

            return (
                False,
                "First order only."
            )

    return (
        True,
        "Coupon valid."
    )