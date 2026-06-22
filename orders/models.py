from django.db import models

from accounts.models import User
from shops.models import Shop
from menu.models import MenuItem


class Order(models.Model):

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("preparing", "Preparing"),
        ("ready", "Ready"),
        ("collected", "Collected"),
        ("cancelled", "Cancelled"),
    )

    PAYMENT_METHODS = (
        ("cash", "Cash On Pickup"),
        ("upi", "UPI On Shop"),
    )

    PAYMENT_STATUS = (
        ("pending", "Pending"),
        ("paid", "Paid"),
    )

    order_number = models.CharField(
        max_length=30,
        unique=True
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default="cash"
    )

    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default="pending"
    )

    pickup_time = models.DateTimeField(
        null=True,
        blank=True
    )

    order_type = models.CharField(
        max_length=20,
        choices=(
            ("online", "Online"),
            ("walkin", "Walk-In"),
        ),
        default="online"
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    customer_name = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    customer_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    ordered_at = models.DateTimeField(
        auto_now_add=True
    )
    
    rejection_reason = models.TextField(
        blank=True,
        null=True
    )

    accepted_at = models.DateTimeField(
        null=True,
        blank=True
    )

    ready_at = models.DateTimeField(
        null=True,
        blank=True
    )

    collected_at = models.DateTimeField(
        null=True,
        blank=True
    )

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    item_name = models.CharField(
        max_length=255
    )

    item_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    quantity = models.PositiveIntegerField()

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    def __str__(self):
        return self.item_name