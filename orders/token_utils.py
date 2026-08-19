# orders/token_utils.py

from django.db import transaction
from delivery.models import WalkInTokenCounter, get_business_date


def assign_walkin_token(order):
    """
    Assign a short token to a walk-in order.
    Called AFTER the order is created.
    """
    if order.order_type != 'walkin':
        return None

    token = WalkInTokenCounter.get_next_token(order.shop)
    business_date = get_business_date()

    with transaction.atomic():
        order.token_number = token
        order.business_date = business_date
        order.save(update_fields=['token_number', 'business_date'])

    return token


def get_walkin_display_token(order):
    """
    Returns the short token for display, or None for online orders.
    """
    return order.token_number if order.order_type == 'walkin' else None