from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):

    def has_permission(self, request, view):

        return (
            request.user.is_authenticated and
            request.user.role == "super_admin"
        )


class IsManager(BasePermission):

    def has_permission(self, request, view):

        return (
            request.user.is_authenticated and
            request.user.role == "manager"
        )


class IsCustomer(BasePermission):

    def has_permission(self, request, view):

        return (
            request.user.is_authenticated and
            request.user.role == "customer"
        )
        
        
from rest_framework.permissions import BasePermission
from orders.models import Order  # adjust import if needed

class IsSuperAdminOrManagerOrSelf(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if user.role in ('super_admin', 'manager'):
            return True
        if user.role == 'customer':
            return True
        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.role == 'super_admin':
            return True
        if user.role == 'manager':
            shop = getattr(user.manager_profile, 'shop', None)
            if shop and Order.objects.filter(customer=obj, shop=shop).exists():   # <-- FIXED
                return True
            return False
        if user.role == 'customer':
            return obj == user
        return False
    

# ============================================================
# NEW PERMISSION: Manager can read own shop
# ============================================================

class CanReadOwnShop(BasePermission):
    """
    Custom permission:
    - Super admin: full access (GET, PUT, PATCH, DELETE)
    - Manager: can only retrieve (GET) their own shop
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        user = request.user
        # Super admin can do anything
        if user.role == 'super_admin':
            return True
        # Manager: allow only safe methods (GET, HEAD, OPTIONS)
        if user.role == 'manager':
            if request.method in ('GET', 'HEAD', 'OPTIONS'):
                try:
                    profile = user.manager_profile
                    # Check if this shop belongs to the manager
                    return profile.shop and profile.shop.id == obj.id
                except:
                    return False
            return False
        # Any other role: no access
        return False