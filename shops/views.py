# shops/views.py

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny, IsAdminUser
from rest_framework.response import Response
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db import transaction
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser  # <-- ADD JSONParser

from accounts.permissions import IsSuperAdmin, CanReadOwnShop
from accounts.models import User, ManagerProfile
from geopy.distance import geodesic
from .models import Shop, ShopOrderCapacityAudit
from .serializers import ShopSerializer
from .services import get_order_capacity_snapshot


class PublicShopListView(generics.ListAPIView):
    queryset = Shop.objects.filter(is_active=True)
    serializer_class = ShopSerializer
    permission_classes = [AllowAny]


class ShopListCreateView(generics.ListCreateAPIView):
    """Only super admin can list all shops and create new shops."""
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser] # Add JSONParser here too for consistency
    permission_classes = [IsAuthenticated, IsSuperAdmin]


class ShopDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    - Super admin: full access (GET, PUT, PATCH, DELETE).
    - Manager: can GET, PUT, PATCH their own shop (to change settings like delivery_assignment_mode),
      but cannot DELETE.
    """
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    # ADD JSONParser here so it accepts both JSON and multipart/form-data
    parser_classes = [MultiPartParser, FormParser, JSONParser] 

    def get_permissions(self):
        """
        Dynamically set permissions based on HTTP method.
        - GET, PUT, PATCH: Allow managers to update their own shop
        - DELETE: Only super admin
        """
        if self.request.method in ['GET', 'PUT', 'PATCH']:
            return [IsAuthenticated(), CanReadOwnShop()]
        elif self.request.method == 'DELETE':
            return [IsAuthenticated(), IsSuperAdmin()]
        return super().get_permissions()

    def perform_update(self, serializer):
        """
        Extra safety check: Ensure manager can only update their own shop.
        """
        user = self.request.user
        if user.role == 'manager':
            try:
                if user.manager_profile.shop != self.get_object():
                    return Response({'error': 'You can only update your own shop.'},
                                    status=status.HTTP_403_FORBIDDEN)
            except:
                return Response({'error': 'Manager profile not found.'},
                                status=status.HTTP_403_FORBIDDEN)
        serializer.save()


# ============================================================
#  BELOW ARE YOUR OTHER VIEWS (No changes needed)
# ============================================================

class AssignManagerView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request):
        manager_id = request.data.get("manager_id")
        shop_id = request.data.get("shop_id")

        try:
            manager = User.objects.get(id=manager_id, role="manager")
            shop = Shop.objects.get(id=shop_id)
            profile, created = ManagerProfile.objects.get_or_create(user=manager)
            profile.shop = shop
            profile.save()
            return Response({"message": "Manager assigned successfully"})
        except User.DoesNotExist:
            return Response({"error": "Manager not found"}, status=status.HTTP_404_NOT_FOUND)
        except Shop.DoesNotExist:
            return Response({"error": "Shop not found"}, status=status.HTTP_404_NOT_FOUND)


class RemoveManagerView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def post(self, request):
        manager_id = request.data.get("manager_id")
        try:
            profile = ManagerProfile.objects.get(user_id=manager_id)
            profile.shop = None
            profile.save()
            return Response({"message": "Manager removed"})
        except ManagerProfile.DoesNotExist:
            return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)


class MyShopView(APIView):
    """Returns the shop assigned to the currently logged‑in manager."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != 'manager':
            return Response({"error": "Only managers can access this endpoint"}, status=403)
        try:
            profile = request.user.manager_profile
            if not profile.shop:
                return Response({"error": "No shop assigned"}, status=404)
            serializer = ShopSerializer(profile.shop)
            return Response(serializer.data)
        except:
            return Response({"error": "Profile not found"}, status=404)


def _manager_shop(request):
    if request.user.role == "manager":
        return getattr(getattr(request.user, "manager_profile", None), "shop", None)
    if request.user.role == "super_admin":
        shop_id = request.query_params.get("shop_id") or request.data.get("shop_id")
        return Shop.objects.filter(id=shop_id).first() if shop_id else Shop.objects.first()
    return None


class OnlineOrderStatusView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        shop_id = request.query_params.get("shop_id")
        shop = Shop.objects.filter(id=shop_id, is_active=True).first()
        if not shop:
            return Response({"error": "Shop not found"}, status=status.HTTP_404_NOT_FOUND)
        requested_date = parse_date(request.query_params.get("date", ""))
        snapshot = get_order_capacity_snapshot(shop, requested_date)
        return Response({
            "accepting_online_orders": snapshot["accepting_online_orders"],
            "reason": snapshot["reason"],
            "active_orders": snapshot["active_online_orders"],
            "maximum_orders": snapshot["max_online_orders"],
            "available_capacity": snapshot["available_capacity"],
            "capacity_date": snapshot["capacity_date"],
        })


class ManagerOrderCapacityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop = _manager_shop(request)
        if not shop:
            return Response({"error": "No shop assigned"}, status=status.HTTP_404_NOT_FOUND)
        requested_date = parse_date(request.query_params.get("date", ""))
        return Response(get_order_capacity_snapshot(shop, requested_date))

    def patch(self, request):
        shop = _manager_shop(request)
        if not shop:
            return Response({"error": "No shop assigned"}, status=status.HTTP_404_NOT_FOUND)
        try:
            maximum = int(request.data.get("max_online_orders"))
        except (TypeError, ValueError):
            return Response({"max_online_orders": "Enter a whole number."}, status=400)
        if not 1 <= maximum <= 1000:
            return Response({"max_online_orders": "Capacity must be between 1 and 1000."}, status=400)
        with transaction.atomic():
            shop = Shop.objects.select_for_update().get(pk=shop.pk)
            old_value = shop.max_online_orders
            shop.max_online_orders = maximum
            shop.save(update_fields=["max_online_orders", "updated_at"])
            if old_value != maximum:
                ShopOrderCapacityAudit.objects.create(
                    shop=shop, manager=request.user, action="capacity_changed",
                    old_value=str(old_value), new_value=str(maximum),
                )
        return Response(get_order_capacity_snapshot(shop))


class PauseOnlineOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        shop = _manager_shop(request)
        if not shop:
            return Response({"error": "No shop assigned"}, status=status.HTTP_404_NOT_FOUND)
        reason = str(request.data.get("reason", "")).strip()[:255]
        with transaction.atomic():
            shop = Shop.objects.select_for_update().get(pk=shop.pk)
            shop.online_orders_manually_paused = True
            shop.manual_pause_reason = reason
            shop.paused_at = timezone.now()
            shop.save(update_fields=["online_orders_manually_paused", "manual_pause_reason", "paused_at", "updated_at"])
            ShopOrderCapacityAudit.objects.create(
                shop=shop, manager=request.user, action="online_ordering_paused", reason=reason,
            )
        return Response(get_order_capacity_snapshot(shop))


class ResumeOnlineOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        shop = _manager_shop(request)
        if not shop:
            return Response({"error": "No shop assigned"}, status=status.HTTP_404_NOT_FOUND)
        with transaction.atomic():
            shop = Shop.objects.select_for_update().get(pk=shop.pk)
            shop.online_orders_manually_paused = False
            shop.manual_pause_reason = ""
            shop.paused_at = None
            shop.save(update_fields=["online_orders_manually_paused", "manual_pause_reason", "paused_at", "updated_at"])
            ShopOrderCapacityAudit.objects.create(
                shop=shop, manager=request.user, action="online_ordering_resumed",
            )
        return Response(get_order_capacity_snapshot(shop))


class ManagerListView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        managers = User.objects.filter(role="manager")
        data = []
        for manager in managers:
            try:
                profile = manager.manager_profile
                shop_name = profile.shop.name if profile.shop else None
            except:
                shop_name = None
            data.append({
                "id": manager.id,
                "username": manager.username,
                "email": manager.email,
                "shop": shop_name,
            })
        return Response(data)


class NearbyShopView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        latitude = float(request.data.get("latitude"))
        longitude = float(request.data.get("longitude"))
        customer_location = (latitude, longitude)

        nearest_shop = None
        nearest_distance = None

        shops = Shop.objects.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False
        )

        for shop in shops:
            shop_location = (float(shop.latitude), float(shop.longitude))
            distance = geodesic(customer_location, shop_location).km
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_shop = shop

        if not nearest_shop:
            return Response({"error": "No shop found"}, status=404)

        return Response({
            "id": nearest_shop.id,
            "name": nearest_shop.name,
            "address": nearest_shop.address,
            "phone": nearest_shop.phone,
            "latitude": nearest_shop.latitude,
            "longitude": nearest_shop.longitude,
            "distance": round(nearest_distance, 2)
        })