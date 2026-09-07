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
        ("unpaid", "Unpaid"),
        ("paid", "Paid"),
    )
    
    PICKUP_TYPES = (
        ("instant", "Prepare Immediately"),
        ("scheduled", "Scheduled Pickup"),
    )
    
    PROMOTION_TYPES = (
        ("none", "None"),
        ("discount", "Discount"),
        ("coupon", "Coupon"),
    )
    
    DELIVERY_OPTIONS = (
        ('pickup', 'Pay at Shop'),
        ('delivery', 'Home Delivery'),
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
        default="unpaid"
    )
    
    promotion_type = models.CharField(
        max_length=20,
        choices=PROMOTION_TYPES,
        default="none"
    )
    
    
    pickup_type = models.CharField(
        max_length=20,
        choices=PICKUP_TYPES,
        default="instant",
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
    
    paid_at = models.DateTimeField(
        null=True,
        blank=True
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
    
    original_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    discount_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    discount = models.ForeignKey(
        "discounts.Discount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )

    discount_name = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    coupon = models.ForeignKey(
        "discounts.Coupon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders"
    )

    notes = models.TextField(
        blank=True,
        null=True
    )
    
    delivery_option = models.CharField(
        max_length=20,
        choices=DELIVERY_OPTIONS,
        default='pickup',
    )

    delivery_address = models.TextField(
        blank=True,
        null=True,
        help_text="Full delivery address (only for delivery option)"
    )
    delivery_latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    delivery_longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
    )

    # Optional: delivery fee
    delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Delivery fee if applicable"
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
    
    estimated_minutes = models.PositiveIntegerField(
    default=15
    )

    estimated_ready_time = models.DateTimeField(
        null=True,
        blank=True
    )
    
    pickup_person_name = models.CharField(
    max_length=200,
    blank=True,
    null=True
    )

    pickup_person_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )
    
    pickup_by_other_person = models.BooleanField(
        default=False
    )
    

    def __str__(self):
        return self.order_number

    class Meta:
        indexes = [
            models.Index(fields=["shop", "order_type", "status"]),
        ]
    
    @property
    def is_paid(self):
        return self.payment_status == "paid"


    @property
    def payment_badge(self):
        if self.payment_status == "paid":
            return "Paid"
        return "Unpaid"


class OrderItem(models.Model):

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items"
    )

    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    discount = models.ForeignKey(
        "discounts.Discount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    item_name = models.CharField(
        max_length=255
    )

    original_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )

    final_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    quantity = models.PositiveIntegerField()

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    discount_name = models.CharField(
        max_length=200,
        blank=True,
        null=True
    )

    discount_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    promotion_type = models.CharField(
        max_length=20,
        choices=Order.PROMOTION_TYPES,
        default="none"
    )

    def __str__(self):
        return self.item_name
    

# ==========================================
# WALK-IN DRAFT CART
# ==========================================

class WalkInCart(models.Model):

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("placed", "Placed"),
        ("cancelled", "Cancelled"),
    )
    
    PAYMENT_STATUS = (
        ("unpaid", "Unpaid"),
        ("paid", "Paid"),
    )

    cart_number = models.CharField(
        max_length=30,
        unique=True
    )

    manager = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="walkin_carts"
    )

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE,
        related_name="walkin_carts"
    )

    customer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    customer_name = models.CharField(
        max_length=200,
        default="Walk-In Customer"
    )

    customer_phone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    payment_method = models.CharField(
        max_length=20,
        choices=Order.PAYMENT_METHODS,
        default="cash"
    )
    
    payment_status = models.CharField(
        max_length=20,
        choices=Order.PAYMENT_STATUS,
        default="unpaid"
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

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    token_number = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    business_date = models.DateField(null=True, blank=True, db_index=True)

    class Meta:

        ordering = [
            "-updated_at"
        ]

    def __str__(self):

        return f"{self.cart_number} - {self.customer_name}"


# ==========================================
# WALK-IN CART ITEMS
# ==========================================

class WalkInCartItem(models.Model):

    cart = models.ForeignKey(
        WalkInCart,
        on_delete=models.CASCADE,
        related_name="items"
    )

    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE
    )

    item_name = models.CharField(
        max_length=255
    )

    item_price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    quantity = models.PositiveIntegerField(
        default=1
    )

    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def save(self, *args, **kwargs):

        self.total_price = (
            self.item_price *
            self.quantity
        )

        super().save(
            *args,
            **kwargs
        )

        total = 0

        for item in self.cart.items.all():

            total += item.total_price

        self.cart.total_amount = total

        self.cart.save(
            update_fields=[
                "total_amount",
                "updated_at"
            ]
        )

    def delete(self, *args, **kwargs):

        cart = self.cart

        super().delete(
            *args,
            **kwargs
        )

        total = 0

        for item in cart.items.all():

            total += item.total_price

        cart.total_amount = total

        cart.save(
            update_fields=[
                "total_amount",
                "updated_at"
            ]
        )

    def __str__(self):

        return self.item_name