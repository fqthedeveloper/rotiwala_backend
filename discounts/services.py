from decimal import Decimal

from django.utils import timezone

from .models import Discount


def get_active_discounts(shop):

    now = timezone.now()

    return (
        Discount.objects.filter(
            shop=shop,
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
        )
        .order_by("-priority", "-id")
    )


def calculate_discount(price, discount):

    price = Decimal(price)

    if discount.discount_type == "percentage":

        discount_amount = (
            price * Decimal(discount.value)
        ) / Decimal("100")

    else:

        discount_amount = Decimal(
            discount.value
        )

    if (
        discount.maximum_discount_amount
        and discount_amount >
        discount.maximum_discount_amount
    ):

        discount_amount = (
            discount.maximum_discount_amount
        )

    final_price = price - discount_amount

    if final_price < Decimal("0"):

        final_price = Decimal("0")

    return (
        discount_amount.quantize(
            Decimal("0.01")
        ),
        final_price.quantize(
            Decimal("0.01")
        ),
    )


def get_item_discount(menu_item):

    discounts = get_active_discounts(
        menu_item.shop
    )

    for discount in discounts:

        if (
            discount.apply_on == "item"
            and discount.menu_item_id ==
            menu_item.id
        ):

            return discount

    for discount in discounts:

        if (
            discount.apply_on ==
            "category"
            and discount.category_id ==
            menu_item.category_id
        ):

            return discount

    for discount in discounts:

        if discount.apply_on == "shop":

            return discount

    return None


def get_discounted_price(menu_item):

    original_price = Decimal(
        menu_item.base_price
    )

    discount = get_item_discount(
        menu_item
    )

    if not discount:

        return {

            "original_price":
            original_price,

            "discount_amount":
            Decimal("0.00"),

            "final_price":
            original_price,

            "discount": None,

            "has_discount":
            False,

            "discount_percentage":
            None,
        }

    discount_amount, final_price = (
        calculate_discount(
            original_price,
            discount
        )
    )

    percentage = None

    if (
        discount.discount_type
        == "percentage"
    ):

        percentage = int(
            discount.value
        )

    return {

        "original_price":
        original_price,

        "discount_amount":
        discount_amount,

        "final_price":
        final_price,

        "discount":
        discount,

        "has_discount":
        True,

        "discount_percentage":
        percentage,
    }