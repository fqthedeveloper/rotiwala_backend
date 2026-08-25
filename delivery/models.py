# delivery/models.py

import secrets
import string
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import User
from shops.models import Shop
from orders.models import Order


# ============================================================
#  BUSINESS DAY UTILITY
# ============================================================

def get_business_date(dt=None):
    """Returns business date (03:00 AM to 02:59 AM next day)."""
    if dt is None:
        dt = timezone.localtime()
    else:
        dt = timezone.localtime(dt)

    if dt.hour < 3:
        return dt.date() - timezone.timedelta(days=1)
    return dt.date()


# ============================================================
#  WALK-IN TOKEN COUNTER
# ============================================================

class WalkInTokenCounter(models.Model):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='token_counters')
    business_date = models.DateField()
    last_token = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [['shop', 'business_date']]
        indexes = [models.Index(fields=['shop', 'business_date'])]

    def __str__(self):
        return f"{self.shop.shop_code} - {self.business_date} - #{self.last_token}"

    @classmethod
    def get_next_token(cls, shop):
        business_date = get_business_date()
        with transaction.atomic():
            counter, created = cls.objects.select_for_update().get_or_create(
                shop=shop, business_date=business_date, defaults={'last_token': 0}
            )
            counter.last_token += 1
            counter.save(update_fields=['last_token'])
        return str(counter.last_token).zfill(4)


# ============================================================
#  DELIVERY BOY PROFILE
# ============================================================

class DeliveryBoyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='delivery_profile')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='delivery_boys')
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True, null=True)
    photo = models.ImageField(upload_to='delivery_boys/', blank=True, null=True)

    # Online / Availability
    is_online = models.BooleanField(default=False)
    is_available = models.BooleanField(default=True)  # Keep true if not at max capacity
    max_active_orders = models.PositiveIntegerField(default=3)  # NEW - capacity limit

    # Current location
    current_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    last_location_at = models.DateTimeField(null=True, blank=True)

    # Statistics
    total_deliveries = models.PositiveIntegerField(default=0)
    total_distance_km = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['shop', 'is_online', 'is_available'])]

    def __str__(self):
        return f"{self.full_name} ({self.shop.shop_code})"

    def update_location(self, latitude, longitude):
        self.current_latitude = latitude
        self.current_longitude = longitude
        self.last_location_at = timezone.now()
        self.save(update_fields=['current_latitude', 'current_longitude', 'last_location_at'])

    @property
    def active_order_count(self):
        return DeliveryAssignment.objects.filter(
            delivery_boy=self,
            status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery']
        ).count()

    @property
    def has_capacity(self):
        return self.active_order_count < self.max_active_orders


# ============================================================
#  PARCEL
# ============================================================

class Parcel(models.Model):
    STATUS_CHOICES = (
        ('created', 'Created'),
        ('ready', 'Ready'),
        ('assigned', 'Assigned'),
        ('picked_up', 'Picked Up'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='parcel')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='parcels')
    parcel_number = models.CharField(max_length=30, unique=True)
    qr_token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='created')

    created_at = models.DateTimeField(auto_now_add=True)
    scanned_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Parcel {self.parcel_number} - {self.order.order_number}"

    def generate_qr_token(self):
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(64))

    def save(self, *args, **kwargs):
        if not self.parcel_number:
            ts = timezone.now().strftime('%Y%m%d%H%M%S')
            self.parcel_number = f"PAR-{self.shop.shop_code}-{ts}"
        if not self.qr_token:
            self.qr_token = self.generate_qr_token()
        super().save(*args, **kwargs)


# ============================================================
#  DELIVERY ASSIGNMENT
# ============================================================

class DeliveryAssignment(models.Model):
    STATUS_CHOICES = (
        ('assigned', 'Assigned'),
        ('accepted', 'Accepted'),
        ('picked_up', 'Picked Up'),
        ('out_for_delivery', 'Out for Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('reassigned', 'Reassigned'),
    )

    MODE_CHOICES = (
        ('manual', 'Manual'),
        ('auto', 'Automatic'),
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery_assignment')
    parcel = models.OneToOneField(Parcel, on_delete=models.CASCADE, related_name='delivery_assignment', null=True, blank=True)
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='delivery_assignments')
    delivery_boy = models.ForeignKey(DeliveryBoyProfile, on_delete=models.CASCADE, related_name='assignments')

    assignment_mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='manual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned')

    # Timestamps
    assigned_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    out_for_delivery_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    # Distance tracking
    estimated_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actual_distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    previous_assignment = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='next_assignments')

    class Meta:
        indexes = [
            models.Index(fields=['shop', 'status']),
            models.Index(fields=['delivery_boy', 'status']),
        ]

    def __str__(self):
        return f"Assignment #{self.id} - {self.order.order_number} -> {self.delivery_boy.full_name}"

    def can_transition_to(self, new_status):
        transitions = {
            'assigned': ['accepted', 'cancelled', 'reassigned'],
            'accepted': ['picked_up', 'cancelled', 'reassigned'],
            'picked_up': ['out_for_delivery', 'cancelled'],
            'out_for_delivery': ['delivered', 'cancelled'],
            'delivered': [],
            'cancelled': [],
            'reassigned': [],
        }
        return new_status in transitions.get(self.status, [])


# ============================================================
#  DELIVERY LOCATION (GPS History)
# ============================================================

class DeliveryLocation(models.Model):
    delivery_boy = models.ForeignKey(DeliveryBoyProfile, on_delete=models.CASCADE, related_name='locations')
    assignment = models.ForeignKey(DeliveryAssignment, on_delete=models.SET_NULL, null=True, blank=True, related_name='locations')
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    accuracy = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    speed = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['delivery_boy', '-recorded_at']),
            models.Index(fields=['assignment', '-recorded_at']),
        ]

    def __str__(self):
        return f"{self.delivery_boy.full_name} @ {self.recorded_at}"