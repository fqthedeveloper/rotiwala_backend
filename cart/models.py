from django.db import models

from accounts.models import User
from menu.models import MenuItem


class Cart(models.Model):

    customer = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"Cart-{self.customer.username}"


class CartItem(models.Model):

    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items"
    )

    menu_item = models.ForeignKey(
        MenuItem,
        on_delete=models.CASCADE
    )

    variant = models.ForeignKey(
        "menu.MenuItemVariant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    quantity = models.PositiveIntegerField(
        default=1
    )

    added_at = models.DateTimeField(
        auto_now_add=True
    )

    @property
    def unit_price(self):
        if self.variant:
            return self.variant.price
        return self.menu_item.base_price

    @property
    def total_price(self):
        return self.unit_price * self.quantity

    def __str__(self):
        if self.variant:
            return f"{self.menu_item.name} ({self.variant.name})"
        return self.menu_item.name