# delivery/permissions.py

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsDeliveryBoy(BasePermission):
    """Allows access only to users with role 'delivery_boy'."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'delivery_boy'


class IsManagerOrSuperAdmin(BasePermission):
    """Allows access to managers and super admins."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in ('manager', 'super_admin')


class IsOwnShopManager(BasePermission):
    """
    Allows managers to access only their own shop's data.
    Super admins can access all.
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.role == 'super_admin':
            return True
        if request.user.role == 'manager':
            return hasattr(request.user, 'manager_profile') and request.user.manager_profile.shop is not None
        return False

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'super_admin':
            return True
        if request.user.role == 'manager':
            shop = getattr(obj, 'shop', None)
            if shop is None:
                return False
            return request.user.manager_profile.shop == shop
        return False


class IsOwnDeliveryBoy(BasePermission):
    """Allows delivery boys to access only their own assignments."""
    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated or request.user.role != 'delivery_boy':
            return False
        if hasattr(obj, 'delivery_boy'):
            return obj.delivery_boy.user == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        return False