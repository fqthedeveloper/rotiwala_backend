import random
import string

from django.db import models
from django.utils import timezone

from shops.models import Shop
from accounts.models import User


def generate_coupon_code():

    while True:

        code = "".join(

            random.choices(

                string.ascii_uppercase +
                string.digits,

                k=8

            )

        )

        if not Coupon.objects.filter(
            code=code
        ).exists():

            return code


class Coupon(models.Model):

    DISCOUNT_TYPES = (
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    )

    STATUS = (
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("expired", "Expired"),
    )

    code = models.CharField(
        max_length=30,
        unique=True,
        default=generate_coupon_code
    )

    name = models.CharField(
        max_length=200
    )

    description = models.TextField(
        blank=True,
        null=True
    )

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="coupons"
    )

    discount_type = models.CharField(
        max_length=20,
        choices=DISCOUNT_TYPES,
        default="percentage"
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    minimum_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    maximum_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )

    first_order_only = models.BooleanField(
        default=False
    )

    auto_generate = models.BooleanField(
        default=False
    )

    send_notification = models.BooleanField(
        default=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="active"
    )

    start_date = models.DateTimeField()

    end_date = models.DateTimeField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        ordering = [
            "-created_at"
        ]

    def __str__(self):

        return self.code

    @property
    def is_running(self):

        now = timezone.now()

        return (

            self.status == "active"

            and

            self.start_date <= now

            and

            self.end_date >= now

        )
        
class CouponUsage(models.Model):

    ORDER_TYPES = (

        ("online", "Online"),

        ("walkin", "Walk-In"),

    )

    coupon = models.ForeignKey(

        Coupon,

        on_delete=models.CASCADE,

        related_name="usages"

    )

    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="coupon_usages"
    )

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="coupon_usages"
    )
    
    order = models.ForeignKey(

        "orders.Order",

        on_delete=models.CASCADE,

        related_name="coupon_usages"

    )

    order_type = models.CharField(

        max_length=20,

        choices=ORDER_TYPES,

        default="online"

    )

    original_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    final_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    quantity = models.PositiveIntegerField(
        default=1
    )

    created_at = models.DateTimeField(

        auto_now_add=True

    )

    class Meta:
        ordering = [
            "-created_at"
        ]

        constraints = [
            models.UniqueConstraint(
                fields=["coupon", "customer"],
                name="unique_coupon_per_customer"
            )
        ]

    def __str__(self):

        return self.coupon.code