from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from accounts.permissions import IsSuperAdmin


from accounts.models import (
    User,
    ManagerProfile
)

from geopy.distance import geodesic
from .models import Shop
from .serializers import ShopSerializer
from rest_framework.parsers import (
    MultiPartParser,
    FormParser
)


class PublicShopListView(
    generics.ListAPIView
):

    queryset = Shop.objects.filter(
        is_active=True
    )

    serializer_class = ShopSerializer

    permission_classes = [
        AllowAny
    ]


class ShopListCreateView(
    generics.ListCreateAPIView
):

    queryset = Shop.objects.all()

    serializer_class = ShopSerializer

    parser_classes = [
        MultiPartParser,
        FormParser
    ]

    permission_classes = [
        IsAuthenticated
    ]


class ShopDetailView(
    generics.RetrieveUpdateDestroyAPIView
):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer

    parser_classes = [
        MultiPartParser,
        FormParser
    ]

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

class AssignManagerView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def post(self, request):

        manager_id = request.data.get(
            "manager_id"
        )

        shop_id = request.data.get(
            "shop_id"
        )

        try:

            manager = User.objects.get(
                id=manager_id,
                role="manager"
            )

            shop = Shop.objects.get(
                id=shop_id
            )

            profile, created = (
                ManagerProfile.objects.get_or_create(
                    user=manager
                )
            )

            profile.shop = shop

            profile.save()

            return Response(
                {
                    "message":
                    "Manager assigned successfully"
                }
            )

        except User.DoesNotExist:

            return Response(
                {
                    "error":
                    "Manager not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        except Shop.DoesNotExist:

            return Response(
                {
                    "error":
                    "Shop not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )
            

class RemoveManagerView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def post(self, request):

        manager_id = request.data.get(
            "manager_id"
        )

        try:

            profile = (
                ManagerProfile.objects.get(
                    user_id=manager_id
                )
            )

            profile.shop = None

            profile.save()

            return Response({
                "message":
                "Manager removed"
            })

        except ManagerProfile.DoesNotExist:

            return Response(
                {
                    "error":
                    "Profile not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )
            

class MyShopView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        profile = request.user.manager_profile

        if not profile.shop:

            return Response(
                {
                    "error":
                    "No shop assigned"
                },
                status=404
            )

        serializer = ShopSerializer(
            profile.shop
        )

        return Response(
            serializer.data
        )
        
class ManagerListView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def get(self, request):

        managers = User.objects.filter(
            role="manager"
        )

        data = []

        for manager in managers:

            try:

                profile = manager.manager_profile

                shop_name = (
                    profile.shop.name
                    if profile.shop
                    else None
                )

            except:

                shop_name = None

            data.append(
                {
                    "id": manager.id,
                    "username": manager.username,
                    "email": manager.email,
                    "shop": shop_name
                }
            )

        return Response(data)


class NearbyShopView(APIView):

    permission_classes = []

    def post(self, request):

        latitude = float(
            request.data.get("latitude")
        )

        longitude = float(
            request.data.get("longitude")
        )

        customer_location = (
            latitude,
            longitude
        )

        nearest_shop = None

        nearest_distance = None

        shops = Shop.objects.filter(
            is_active=True,
            latitude__isnull=False,
            longitude__isnull=False
        )

        for shop in shops:

            shop_location = (
                float(shop.latitude),
                float(shop.longitude)
            )

            distance = geodesic(
                customer_location,
                shop_location
            ).km

            if (
                nearest_distance is None
                or
                distance < nearest_distance
            ):
                nearest_distance = distance
                nearest_shop = shop

        if not nearest_shop:

            return Response(
                {
                    "error":
                    "No shop found"
                },
                status=404
            )

        return Response({

            "id":
            nearest_shop.id,

            "name":
            nearest_shop.name,

            "address":
            nearest_shop.address,

            "phone":
            nearest_shop.phone,

            "latitude":
            nearest_shop.latitude,

            "longitude":
            nearest_shop.longitude,

            "distance":
            round(
                nearest_distance,
                2
            )
        })