from accounts.models import User

from notifications.fcm import send_push_notification


def send_discount_notification(discount):

    customers = User.objects.filter(
        role="customer",
        is_active=True
    ).exclude(
        fcm_token__isnull=True
    ).exclude(
        fcm_token=""
    )

    title = "🔥 New Offer Available!"

    if discount.discount_type == "percentage":

        body = (
            f"{discount.value}% OFF - {discount.name}"
        )

    else:

        body = (
            f"₹{discount.value} OFF - {discount.name}"
        )

    success = 0
    failed = 0

    for customer in customers:

        result = send_push_notification(

            token=customer.fcm_token,

            title=title,

            body=body,

            data={
                "type": "discount",
                "discount_id": str(discount.id),
                "shop_id": str(discount.shop.id),
            }

        )

        if result:
            success += 1
        else:
            failed += 1

    return {
        "success": success,
        "failed": failed,
    }