from decimal import Decimal

from django.db import models
from django.utils import timezone

from shops.models import Shop
from menu.models import MenuCategory, MenuItem


class Discount(models.Model):

    DISCOUNT_TYPES = (
        ("percentage", "Percentage"),
        ("fixed", "Fixed Amount"),
    )

    APPLY_ON = (
        ("shop", "Entire Shop"),
        ("category", "Category"),
        ("item", "Menu Item"),
    )

    # ===============================
    # BASIC DETAILS
    # ===============================

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
        related_name="discounts"
    )

    apply_on = models.CharField(
        max_length=20,
        choices=APPLY_ON,
        default="shop"
    )

    category = models.ForeignKey(
        MenuCategory,
        on_delete=models.CASCADE,
        related_name="discounts",
        blank=True,
        null=True
    )

    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE,
        related_name="discounts",
        blank=True,
        null=True
    )

    # ===============================
    # DISCOUNT
    # ===============================

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

    # ===============================
    # CUSTOMER DISPLAY
    # ===============================

    banner_image = models.ImageField(
        upload_to="discounts/",
        blank=True,
        null=True
    )

    badge_text = models.CharField(
        max_length=40,
        default="SALE"
    )

    banner_color = models.CharField(
        max_length=20,
        default="#FF9800"
    )

    notification_title = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    notification_body = models.TextField(
        blank=True,
        null=True
    )

    terms_and_conditions = models.TextField(
        blank=True,
        null=True
    )

    # ===============================
    # DISPLAY SETTINGS
    # ===============================

    featured = models.BooleanField(
        default=False
    )

    display_order = models.PositiveIntegerField(
        default=1
    )

    priority = models.PositiveIntegerField(
        default=1
    )

    # ===============================
    # DATE
    # ===============================

    start_date = models.DateTimeField()

    end_date = models.DateTimeField()

    # ===============================
    # SETTINGS
    # ===============================

    is_active = models.BooleanField(
        default=True
    )

    send_notification = models.BooleanField(
        default=True
    )

    # ===============================
    # AUDIT
    # ===============================

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:

        ordering = [
            "-featured",
            "display_order",
            "-priority",
            "-created_at",
        ]

    def __str__(self):

        return self.name

    @property
    def is_running(self):

        now = timezone.now()

        return (
            self.is_active
            and self.start_date <= now
            and self.end_date >= now
        )

    @property
    def status(self):

        now = timezone.now()

        if not self.is_active:
            return "Inactive"

        if now < self.start_date:
            return "Upcoming"

        if self.start_date <= now <= self.end_date:
            return "Active"

        return "Expired"

    @property
    def banner(self):

        if self.banner_image:
            return self.banner_image.url

        return None

    @property
    def discount_text(self):

        if self.discount_type == "percentage":
            return f"{int(self.value)}% OFF"

        return f"₹{self.value} OFF"

    @property
    def notification_heading(self):

        if self.notification_title:
            return self.notification_title

        return "🎉 New Offer"

    @property
    def notification_message(self):

        if self.notification_body:
            return self.notification_body

        return f"{self.discount_text} - {self.name}"


class DiscountUsage(models.Model):

    ORDER_TYPES = (
        ("online", "Online"),
        ("walkin", "Walk-In"),
    )

    discount = models.ForeignKey(
        Discount,
        on_delete=models.CASCADE,
        related_name="usages"
    )

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="discount_usages"
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="discounts_used"
    )

    customer = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="discounts_used"
    )

    order_type = models.CharField(
        max_length=20,
        choices=ORDER_TYPES,
        default="online"
    )

    discount_type = models.CharField(
        max_length=20
    )

    discount_value = models.DecimalField(
        max_digits=10,
        decimal_places=2
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
                fields=["discount", "customer"],
                name="unique_discount_per_customer"
            )
        ]

    def __str__(self):
        return (
            f"{self.discount.name} - "
            f"{self.shop.name} - "
            f"{self.order.order_number}"
        )