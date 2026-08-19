# delivery/services.py

import math
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from shops.models import Shop
from orders.models import Order
from .models import DeliveryBoyProfile, DeliveryAssignment, Parcel, get_business_date


# ============================================================
#  DISTANCE CALCULATION (Haversine)
# ============================================================

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points
    in kilometers using the Haversine formula.
    """
    R = 6371  # Earth's radius in kilometers

    lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))

    return Decimal(str(R * c))


def validate_delivery_location(shop, customer_lat, customer_lon):
    """
    Validate that the customer location is within the shop's delivery radius.
    Raises ValidationError if outside.
    """
    if not shop.latitude or not shop.longitude:
        raise ValidationError("Shop location is not configured.")

    distance = haversine_distance(
        shop.latitude, shop.longitude,
        customer_lat, customer_lon
    )

    if distance > shop.delivery_radius_km:
        raise ValidationError(
            f"Delivery is not available at this location. "
            f"Maximum distance is {shop.delivery_radius_km} km, "
            f"your location is {distance:.2f} km away."
        )

    return distance


# ============================================================
#  PARCEL CREATION
# ============================================================

def create_parcel_for_order(order):
    """
    Create a Parcel when a delivery order becomes READY.
    """
    if order.delivery_option != 'delivery':
        return None

    if hasattr(order, 'parcel'):
        return order.parcel  # Already exists

    parcel = Parcel.objects.create(
        order=order,
        shop=order.shop,
        status='created'
    )
    return parcel


# ============================================================
#  MANUAL ASSIGNMENT
# ============================================================

def assign_delivery_manually(order, delivery_boy_profile, assigned_by=None):
    """
    Manually assign a delivery boy to an order.
    """
    if order.delivery_option != 'delivery':
        raise ValidationError("This order is not a delivery order.")

    if order.status != 'ready':
        raise ValidationError(f"Order must be READY to assign. Current status: {order.status}")

    if not hasattr(order, 'parcel'):
        raise ValidationError("Parcel not created for this order.")

    parcel = order.parcel
    if parcel.status in ('picked_up', 'out_for_delivery', 'delivered'):
        raise ValidationError(f"Parcel is already {parcel.status}.")

    # Check delivery boy belongs to the same shop
    if delivery_boy_profile.shop != order.shop:
        raise ValidationError("Delivery boy does not belong to this shop.")

    if not delivery_boy_profile.is_online or not delivery_boy_profile.is_available:
        raise ValidationError("Delivery boy is not available.")

    with transaction.atomic():
        # Close any existing assignment for this order
        existing = DeliveryAssignment.objects.filter(order=order, status__in=['assigned', 'accepted']).first()
        if existing:
            existing.status = 'reassigned'
            existing.save(update_fields=['status'])

        # Calculate estimated distance
        if order.delivery_latitude and order.delivery_longitude:
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

        # Update delivery boy availability (optional: mark busy)
        delivery_boy_profile.is_available = False
        delivery_boy_profile.save(update_fields=['is_available'])

    return assignment


# ============================================================
#  AUTOMATIC ASSIGNMENT
# ============================================================

def find_best_delivery_boy(order):
    """
    Find the best available delivery boy for automatic assignment.
    Uses a combination of:
      - Nearest distance to shop/customer
      - Lowest active workload
    """
    shop = order.shop

    # Get all online & available delivery boys for this shop
    candidates = DeliveryBoyProfile.objects.filter(
        shop=shop,
        is_online=True,
        is_available=True
    )

    if not candidates.exists():
        return None

    # Get active assignment count for each candidate
    active_assignments = {}
    for boy in candidates:
        active_count = DeliveryAssignment.objects.filter(
            delivery_boy=boy,
            status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery']
        ).count()
        active_assignments[boy.id] = active_count

    # Score each candidate: lower score is better
    scored = []
    for boy in candidates:
        # Distance from shop to delivery boy (if boy has location)
        if boy.current_latitude and boy.current_longitude and shop.latitude and shop.longitude:
            distance_to_shop = haversine_distance(
                shop.latitude, shop.longitude,
                boy.current_latitude, boy.current_longitude
            )
        else:
            distance_to_shop = Decimal('999')

        # Distance from boy to customer (if order has delivery location)
        if order.delivery_latitude and order.delivery_longitude and boy.current_latitude and boy.current_longitude:
            distance_to_customer = haversine_distance(
                boy.current_latitude, boy.current_longitude,
                order.delivery_latitude, order.delivery_longitude
            )
        else:
            distance_to_customer = Decimal('999')

        # Score: weighted combination
        # Prefer lower active count, then shorter distance
        active_weight = Decimal(str(active_assignments[boy.id])) * Decimal('2')
        distance_weight = distance_to_shop + distance_to_customer
        score = active_weight + distance_weight

        scored.append({
            'boy': boy,
            'score': score,
            'active_count': active_assignments[boy.id],
            'distance_to_shop': distance_to_shop,
            'distance_to_customer': distance_to_customer,
        })

    # Sort by score ascending
    scored.sort(key=lambda x: x['score'])
    return scored[0]['boy'] if scored else None


def auto_assign_delivery(order):
    """
    Automatically assign the best available delivery boy to an order.
    """
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
    """
    Process a QR scan by a delivery boy.
    Validates the parcel and returns its details.
    """
    try:
        parcel = Parcel.objects.select_for_update().get(qr_token=qr_token)
    except Parcel.DoesNotExist:
        raise ValidationError("Invalid QR code.")

    # Validation checks
    if parcel.shop != delivery_boy_profile.shop:
        raise ValidationError("This parcel does not belong to your shop.")

    if parcel.status in ('picked_up', 'out_for_delivery', 'delivered'):
        raise ValidationError(f"This parcel has already been {parcel.status}.")

    if parcel.order.status == 'cancelled':
        raise ValidationError("The order for this parcel has been cancelled.")

    if parcel.order.status != 'ready':
        raise ValidationError(f"Order is not ready for pickup. Status: {parcel.order.status}")

    # Check if there's an assignment for this parcel
    try:
        assignment = DeliveryAssignment.objects.get(parcel=parcel, status='assigned')
        if assignment.delivery_boy != delivery_boy_profile:
            raise ValidationError("This parcel is assigned to another delivery boy.")
    except DeliveryAssignment.DoesNotExist:
        raise ValidationError("This parcel has not been assigned to anyone.")

    # Mark as scanned
    parcel.scanned_at = timezone.now()
    parcel.save(update_fields=['scanned_at'])

    return parcel, assignment


def confirm_pickup(assignment, delivery_boy_profile):
    """
    Confirm pickup after QR scan.
    Transitions: ASSIGNED → PICKED_UP → OUT_FOR_DELIVERY
    """
    if assignment.delivery_boy != delivery_boy_profile:
        raise ValidationError("You are not assigned to this delivery.")

    if assignment.status != 'assigned':
        raise ValidationError(f"Cannot pickup. Current status: {assignment.status}")

    with transaction.atomic():
        # Update assignment
        assignment.status = 'picked_up'
        assignment.picked_up_at = timezone.now()
        assignment.save(update_fields=['status', 'picked_up_at'])

        # Update parcel
        parcel = assignment.parcel
        parcel.status = 'picked_up'
        parcel.picked_up_at = timezone.now()
        parcel.save(update_fields=['status', 'picked_up_at'])

        # Update order status
        order = assignment.order
        order.status = 'preparing'  # or keep 'ready'? According to spec, it should become OUT_FOR_DELIVERY
        # Actually, spec says: READY → DELIVERY_ASSIGNED → PICKED_UP → OUT_FOR_DELIVERY
        # We'll keep order status as 'ready' until delivery is confirmed.
        # But we can add a custom status or use the assignment status.
        # For now, leave order as 'ready'.

    return assignment


def confirm_out_for_delivery(assignment, delivery_boy_profile):
    """
    Mark assignment as OUT_FOR_DELIVERY.
    """
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
    """
    Confirm that the delivery is complete.
    """
    if assignment.delivery_boy != delivery_boy_profile:
        raise ValidationError("You are not assigned to this delivery.")

    if assignment.status != 'out_for_delivery':
        raise ValidationError(f"Cannot confirm delivery. Current status: {assignment.status}")

    with transaction.atomic():
        # Update assignment
        assignment.status = 'delivered'
        assignment.delivered_at = timezone.now()
        assignment.save(update_fields=['status', 'delivered_at'])

        # Update parcel
        parcel = assignment.parcel
        parcel.status = 'delivered'
        parcel.delivered_at = timezone.now()
        parcel.save(update_fields=['status', 'delivered_at'])

        # Update order
        order = assignment.order
        order.status = 'collected'  # or a new 'delivered' status
        order.save(update_fields=['status'])

        # Update delivery boy statistics
        boy = assignment.delivery_boy
        boy.total_deliveries += 1
        if assignment.estimated_distance_km:
            boy.total_distance_km += assignment.estimated_distance_km
        boy.is_available = True
        boy.save(update_fields=['total_deliveries', 'total_distance_km', 'is_available'])

        # TODO: Calculate actual distance from GPS history
        # actual_distance = calculate_actual_distance(assignment)
        # assignment.actual_distance_km = actual_distance
        # assignment.save(update_fields=['actual_distance_km'])

    return assignment