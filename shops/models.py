from django.db import models


class Shop(models.Model):

    name = models.CharField(
        max_length=255
    )
    
    shop_code = models.CharField(
        max_length=10,
        unique=True,
        blank=True,
        null=True
    )

    logo = models.ImageField(
        upload_to="shops/logos/",
        blank=True,
        null=True
    )

    banner = models.ImageField(
        upload_to="shops/banners/",
        blank=True,
        null=True
    )

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )

    phone = models.CharField(
        max_length=20
    )

    address = models.TextField()

    phone = models.CharField(
        max_length=20
    )

    email = models.EmailField(
        blank=True,
        null=True
    )

    opening_time = models.TimeField(
        blank=True,
        null=True
    )

    closing_time = models.TimeField(
        blank=True,
        null=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )
    
    delivery_enabled = models.BooleanField(default=True)
    delivery_radius_km = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=2.00,
        help_text="Maximum delivery radius in kilometers"
    )
    delivery_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Delivery fee charged below the free-delivery threshold"
    )
    free_delivery_min_order = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Minimum discounted subtotal required for free delivery; zero means always free"
    )
    minimum_delivery_order = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Minimum discounted subtotal required to select delivery"
    )
    delivery_assignment_mode = models.CharField(
        max_length=10,
        choices=(('manual', 'Manual'), ('auto', 'Automatic')),
        default='manual'
    )

    max_online_orders = models.PositiveIntegerField(default=100)
    online_orders_manually_paused = models.BooleanField(default=False)
    manual_pause_reason = models.CharField(max_length=255, blank=True, null=True)
    paused_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):

        creating = self.pk is None

        super().save(*args, **kwargs)

        if creating and not self.shop_code:

            self.shop_code = f"RT{self.id}"

            super().save(update_fields=["shop_code"])


class ShopOrderCapacityAudit(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name="order_capacity_audits")
    manager = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="order_capacity_audits",
    )
    action = models.CharField(max_length=40)
    old_value = models.CharField(max_length=255, blank=True)
    new_value = models.CharField(max_length=255, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["shop", "created_at"])]
    

class ShopMenuItem(models.Model):

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE
    )

    menu_item = models.ForeignKey(
        "menu.MenuItem",
        on_delete=models.CASCADE
    )

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    is_available = models.BooleanField(
        default=True
    )

    stock = models.PositiveIntegerField(
        default=999
    )

    class Meta:

        unique_together = (
            "shop",
            "menu_item"
        )