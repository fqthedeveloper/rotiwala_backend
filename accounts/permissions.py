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