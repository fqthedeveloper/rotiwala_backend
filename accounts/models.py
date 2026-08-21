# accounts/models.py

from django.contrib.auth.models import AbstractUser
from django.db import models
from shops.models import Shop


class User(AbstractUser):
    ROLE_CHOICES = (
        ("super_admin", "Super Admin"),
        ("manager", "Manager"),
        ("customer", "Customer"),
        ("delivery_boy", "Delivery Boy"),
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="customer"
    )

    phone = models.CharField(
        max_length=20,
        unique=True
    )

    firebase_uid = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True
    )

    email = models.EmailField(
        blank=True,
        null=True
    )

    fcm_token = models.TextField(
        blank=True,
        null=True
    )

    is_phone_verified = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.phone} ({self.role})"


class CustomerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE
    )

    trust_score = models.IntegerField(
        default=100
    )

    total_orders = models.IntegerField(
        default=0
    )

    total_completed_orders = models.IntegerField(
        default=0
    )

    total_cancelled_orders = models.IntegerField(
        default=0
    )

    total_rejected_orders = models.IntegerField(
        default=0
    )

    is_flagged = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.user.username


class ManagerProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="manager_profile"
    )

    shop = models.OneToOneField(
        "shops.Shop",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manager"
    )

    full_name = models.CharField(
        max_length=255
    )

    phone = models.CharField(
        max_length=20,
        blank=True,
        null=True
    )

    photo = models.ImageField(
        upload_to="managers/",
        blank=True,
        null=True
    )

    address = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.full_name


class CustomerFlag(models.Model):
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="customer_flags"
    )

    flagged_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="flagged_customers"
    )

    reason = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.customer.username}"


# ============================================================
# NEW: Customer Delivery Address
# ============================================================

class CustomerDeliveryAddress(models.Model):
    """
    Saved delivery addresses for customers.
    """
    customer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='delivery_addresses'
    )
    label = models.CharField(
        max_length=50,
        default='Home',
        help_text="e.g., Home, Work, Office"
    )
    address = models.TextField()
    
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6
    )

    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6
    )
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-updated_at']
        unique_together = [['customer', 'latitude', 'longitude']]  # avoid duplicates

    def __str__(self):
        return f"{self.customer.get_full_name()} - {self.label} ({self.address[:30]})"

    def save(self, *args, **kwargs):
        # If this address is set as default, unset any other default for the same customer
        if self.is_default:
            CustomerDeliveryAddress.objects.filter(
                customer=self.customer, is_default=True
            ).exclude(id=self.id).update(is_default=False)
        super().save(*args, **kwargs)