# menu/views.py

from rest_framework import generics
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import MultiPartParser, FormParser

from .models import MenuCategory, MenuItem
from .serializers import MenuCategorySerializer, MenuItemSerializer
from shops.models import Shop


# ============================================
# PUBLIC VIEWS (for customers)
# ============================================

class PublicCategoryListView(generics.ListAPIView):
    """List all active categories (global)."""
    serializer_class = MenuCategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return MenuCategory.objects.filter(is_active=True)


class PublicShopCategoryView(generics.ListAPIView):
    """List all active categories (legacy - ignores shop_id)."""
    serializer_class = MenuCategorySerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        return MenuCategory.objects.filter(is_active=True)


class PublicMenuItemListView(generics.ListAPIView):
    """Public: list available menu items, filterable by category and shop."""
    serializer_class = MenuItemSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        queryset = MenuItem.objects.filter(is_available=True)
        
        category_id = self.request.GET.get("category")
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        shop_id = self.request.GET.get("shop")
        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)
        
        return queryset


class PublicMenuItemDetailView(generics.RetrieveAPIView):
    """Retrieve a single menu item."""
    queryset = MenuItem.objects.filter(is_available=True)
    serializer_class = MenuItemSerializer
    permission_classes = [AllowAny]


class PublicCategoryItemsView(generics.ListAPIView):
    """List all available menu items for a specific category."""
    serializer_class = MenuItemSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        category_id = self.kwargs["category_id"]
        return MenuItem.objects.filter(category_id=category_id, is_available=True)


# ============================================
# ADMIN / MANAGER VIEWS
# ============================================

class CategoryListCreateView(generics.ListCreateAPIView):
    """Categories are global – all authenticated users can view and create."""
    serializer_class = MenuCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MenuCategory.objects.all()

    def perform_create(self, serializer):
        serializer.save()


class CategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Detail, update, delete for a category."""
    serializer_class = MenuCategorySerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    queryset = MenuCategory.objects.all()


class MenuItemListCreateView(generics.ListCreateAPIView):
    """
    Menu items are shop‑specific.
    - Managers: shop is forced to their own.
    - Super Admins: must provide 'shop' in request data.
    """
    serializer_class = MenuItemSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        if user.role == "super_admin":
            return MenuItem.objects.all()
        if user.role == "manager":
            try:
                shop = user.manager_profile.shop
                return MenuItem.objects.filter(shop=shop)
            except AttributeError:
                return MenuItem.objects.none()
        return MenuItem.objects.none()

    def perform_create(self, serializer):
        user = self.request.user

        if user.role == "manager":
            serializer.save(shop=user.manager_profile.shop)
        elif user.role == "super_admin":
            shop_id = self.request.data.get('shop')
            if not shop_id:
                raise DRFValidationError({"shop": "This field is required for super_admin."})
            try:
                shop = Shop.objects.get(id=shop_id)
            except Shop.DoesNotExist:
                raise DRFValidationError({"shop": "Invalid shop ID."})
            serializer.save(shop=shop)
        else:
            raise DRFValidationError({"detail": "Not authorized."})


class MenuItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Detail, update, delete for a menu item."""
    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]