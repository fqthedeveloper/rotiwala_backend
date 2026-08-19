# delivery/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from orders.models import Order
from .services import create_parcel_for_order, auto_assign_delivery
from .consumers import notify_delivery_assignment


@receiver(post_save, sender=Order)
def handle_order_ready(sender, instance, created, **kwargs):
    """When an order becomes READY, create parcel and auto-assign if enabled."""
    if instance.status == 'ready' and instance.delivery_option == 'delivery':
        parcel = create_parcel_for_order(instance)
        if parcel and instance.shop.delivery_assignment_mode == 'auto':
            try:
                assignment = auto_assign_delivery(instance)
                notify_delivery_assignment(assignment)
            except Exception as e:
                # Log error
                pass