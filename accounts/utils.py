# accounts/utils.py
from orders.models import Order

def manager_can_access_customer(manager_user, customer_user):
    """
    Returns True if the manager's shop has orders from this customer.
    """
    if manager_user.role != 'manager':
        return False
    shop = getattr(manager_user.manager_profile, 'shop', None)
    if not shop:
        return False
    return Order.objects.filter(shop=shop, user=customer_user).exists()