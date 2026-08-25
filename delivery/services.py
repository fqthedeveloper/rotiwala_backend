# delivery/services.py

import math
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from shops.models import Shop
from orders.models import Order
from .models import DeliveryBoyProfile, DeliveryAssignment, Parcel, get_business_date


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in km."""
    R = 6371
    lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    return Decimal(str(R * c))


def validate_delivery_location(shop, customer_lat, customer_lon):
    if not shop.latitude or not shop.longitude:
        raise ValidationError("Shop location is not configured.")
    distance = haversine_distance(shop.latitude, shop.longitude, customer_lat, customer_lon)
    if distance > shop.delivery_radius_km:
        raise ValidationError(
            f"Delivery is not available at this location. "
            f"Maximum distance is {shop.delivery_radius_km} km, "
            f"your location is {distance:.2f} km away."
        )
    return distance


def create_parcel_for_order(order):
    if order.delivery_option != 'delivery':
        return None
    if hasattr(order, 'parcel'):
        return order.parcel
    parcel = Parcel.objects.create(order=order, shop=order.shop, status='created')
    return parcel


# ============================================================
#  MANUAL ASSIGNMENT (allowing multiple orders per boy)
# ============================================================

def assign_delivery_manually(order, delivery_boy_profile, assigned_by=None):
    if order.delivery_option != 'delivery':
        raise ValidationError("This order is not a delivery order.")

    if order.status != 'ready':
        raise ValidationError(f"Order must be READY to assign. Current status: {order.status}")

    if not hasattr(order, 'parcel'):
        raise ValidationError("Parcel not created for this order.")

    parcel = order.parcel
    if parcel.status in ('picked_up', 'out_for_delivery', 'delivered'):
        raise ValidationError(f"Parcel is already {parcel.status}.")

    if delivery_boy_profile.shop != order.shop:
        raise ValidationError("Delivery boy does not belong to this shop.")

    # Check if boy has capacity
    if not delivery_boy_profile.has_capacity:
        raise ValidationError(f"Delivery boy already has {delivery_boy_profile.active_order_count} active orders (max {delivery_boy_profile.max_active_orders}).")

    # Boy must be online
    if not delivery_boy_profile.is_online:
        raise ValidationError("Delivery boy is offline.")

    with transaction.atomic():
        # Close existing assignment for this order (if any)
        existing = DeliveryAssignment.objects.filter(order=order, status__in=['assigned', 'accepted']).first()
        if existing:
            existing.status = 'reassigned'
            existing.save(update_fields=['status'])

        # Calculate estimated distance
        if order.delivery_latitude and order.delivery_longitude and order.shop.latitude and order.shop.longitude:
            estimated_distance = haversine_distance(
                order.shop.latitude, order.shop.longitude,
                order.delivery_latitude, order.delivery_longitude
            )
        else:
            estimated_distance = None

        # Create assignment
        assignment = DeliveryAssignment.objects.create(
            order=order,
            parcel=parcel,
            shop=order.shop,
            delivery_boy=delivery_boy_profile,
            assignment_mode='manual',
            status='assigned',
            estimated_distance_km=estimated_distance,
            previous_assignment=existing
        )

        # Update parcel status
        parcel.status = 'assigned'
        parcel.save(update_fields=['status'])

        # DON'T set is_available = False. Keep boy available until capacity is reached.
        # Optionally, update availability based on capacity
        if not delivery_boy_profile.has_capacity:
            delivery_boy_profile.is_available = False
            delivery_boy_profile.save(update_fields=['is_available'])

    return assignment


# ============================================================
#  AUTOMATIC ASSIGNMENT
# ============================================================

def find_best_delivery_boy(order):
    shop = order.shop

    # Get online boys with capacity
    candidates = DeliveryBoyProfile.objects.filter(
        shop=shop,
        is_online=True,
    ).exclude(
        # Exclude those who are at max capacity
        id__in=[
            boy.id for boy in DeliveryBoyProfile.objects.filter(shop=shop, is_online=True)
            if boy.active_order_count >= boy.max_active_orders
        ]
    )

    if not candidates.exists():
        return None

    # Score each candidate
    scored = []
    for boy in candidates:
        # Distance from shop to boy
        if boy.current_latitude and boy.current_longitude and shop.latitude and shop.longitude:
            distance_to_shop = haversine_distance(
                shop.latitude, shop.longitude,
                boy.current_latitude, boy.current_longitude
            )
        else:
            distance_to_shop = Decimal('999')

        # Distance from boy to customer
        if order.delivery_latitude and order.delivery_longitude and boy.current_latitude and boy.current_longitude:
            distance_to_customer = haversine_distance(
                boy.current_latitude, boy.current_longitude,
                order.delivery_latitude, order.delivery_longitude
            )
        else:
            distance_to_customer = Decimal('999')

        # Score: lower active count + shorter distance
        active_weight = Decimal(str(boy.active_order_count)) * Decimal('2')
        distance_weight = distance_to_shop + distance_to_customer
        score = active_weight + distance_weight

        scored.append({
            'boy': boy,
            'score': score,
            'active_count': boy.active_order_count,
            'distance_to_shop': distance_to_shop,
            'distance_to_customer': distance_to_customer,
        })

    scored.sort(key=lambda x: x['score'])
    return scored[0]['boy'] if scored else None


def auto_assign_delivery(order):
    if order.delivery_option != 'delivery':
        raise ValidationError("This order is not a delivery order.")

    if order.status != 'ready':
        raise ValidationError(f"Order must be READY to assign. Current status: {order.status}")

    if not hasattr(order, 'parcel'):
        raise ValidationError("Parcel not created for this order.")

    if order.shop.delivery_assignment_mode != 'auto':
        raise ValidationError("Automatic assignment is not enabled for this shop.")

    best_boy = find_best_delivery_boy(order)
    if not best_boy:
        raise ValidationError("No available delivery boys found.")

    return assign_delivery_manually(order, best_boy)


# ============================================================
#  QR SCAN & PICKUP
# ============================================================

def scan_parcel(qr_token, delivery_boy_profile):
    try:
        parcel = Parcel.objects.select_for_update().get(qr_token=qr_token)
    except Parcel.DoesNotExist:
        raise ValidationError("Invalid QR code.")

    if parcel.shop != delivery_boy_profile.shop:
        raise ValidationError("This parcel does not belong to your shop.")

    if parcel.status in ('picked_up', 'out_for_delivery', 'delivered'):
        raise ValidationError(f"This parcel has already been {parcel.status}.")

    if parcel.order.status == 'cancelled':
        raise ValidationError("The order for this parcel has been cancelled.")

    if parcel.order.status != 'ready':
        raise ValidationError(f"Order is not ready for pickup. Status: {parcel.order.status}")

    try:
        assignment = DeliveryAssignment.objects.get(parcel=parcel, status='assigned')
        if assignment.delivery_boy != delivery_boy_profile:
            raise ValidationError("This parcel is assigned to another delivery boy.")
    except DeliveryAssignment.DoesNotExist:
        raise ValidationError("This parcel has not been assigned to anyone.")

    parcel.scanned_at = timezone.now()
    parcel.save(update_fields=['scanned_at'])

    return parcel, assignment


def confirm_pickup(assignment, delivery_boy_profile):
    if assignment.delivery_boy != delivery_boy_profile:
        raise ValidationError("You are not assigned to this delivery.")

    if assignment.status != 'assigned':
        raise ValidationError(f"Cannot pickup. Current status: {assignment.status}")

    with transaction.atomic():
        assignment.status = 'picked_up'
        assignment.picked_up_at = timezone.now()
        assignment.save(update_fields=['status', 'picked_up_at'])

        parcel = assignment.parcel
        parcel.status = 'picked_up'
        parcel.picked_up_at = timezone.now()
        parcel.save(update_fields=['status', 'picked_up_at'])

    return assignment


def confirm_out_for_delivery(assignment, delivery_boy_profile):
    if assignment.delivery_boy != delivery_boy_profile:
        raise ValidationError("You are not assigned to this delivery.")

    if assignment.status != 'picked_up':
        raise ValidationError(f"Cannot mark out for delivery. Current status: {assignment.status}")

    with transaction.atomic():
        assignment.status = 'out_for_delivery'
        assignment.out_for_delivery_at = timezone.now()
        assignment.save(update_fields=['status', 'out_for_delivery_at'])

        parcel = assignment.parcel
        parcel.status = 'out_for_delivery'
        parcel.save(update_fields=['status'])

    return assignment


# ============================================================
#  DELIVERY CONFIRMATION
# ============================================================

def confirm_delivery(assignment, delivery_boy_profile):
    if assignment.delivery_boy != delivery_boy_profile:
        raise ValidationError("You are not assigned to this delivery.")

    if assignment.status != 'out_for_delivery':
        raise ValidationError(f"Cannot confirm delivery. Current status: {assignment.status}")

    with transaction.atomic():
        assignment.status = 'delivered'
        assignment.delivered_at = timezone.now()
        assignment.save(update_fields=['status', 'delivered_at'])

        parcel = assignment.parcel
        parcel.status = 'delivered'
        parcel.delivered_at = timezone.now()
        parcel.save(update_fields=['status', 'delivered_at'])

        order = assignment.order
        order.status = 'collected'
        order.save(update_fields=['status'])

        boy = assignment.delivery_boy
        boy.total_deliveries += 1
        if assignment.estimated_distance_km:
            boy.total_distance_km += assignment.estimated_distance_km

        # Recalculate availability based on capacity
        if not boy.has_capacity:
            boy.is_available = False
        else:
            boy.is_available = True
        boy.save(update_fields=['total_deliveries', 'total_distance_km', 'is_available'])

    return assignment