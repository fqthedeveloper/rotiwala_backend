from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .coupon_models import (
    Coupon,
)

from .serializers_coupon import (
    CouponSerializer,
)

from .notification import (
    send_discount_notification,
)

class CouponListCreateView(
    generics.ListCreateAPIView
):

    serializer_class = CouponSerializer

    permission_classes = [
        IsAuthenticated
    ]

    def get_queryset(self):

        user = self.request.user

        qs = Coupon.objects.all()

        if user.role == "manager":

            qs = qs.filter(
                shop=user.manager_profile.shop
            )

        shop = self.request.GET.get(
            "shop"
        )

        if shop:

            qs = qs.filter(
                shop_id=shop
            )

        status = self.request.GET.get(
            "status"
        )

        if status:

            qs = qs.filter(
                status=status
            )

        search = self.request.GET.get(
            "search"
        )

        if search:

            qs = qs.filter(

                Q(name__icontains=search)

                |

                Q(code__icontains=search)

            )

        return qs.order_by(
            "-created_at"
        )

    def perform_create(
        self,
        serializer
    ):

        user = self.request.user

        if user.role == "manager":

            coupon = serializer.save(
                shop=user.manager_profile.shop
            )

        else:

            coupon = serializer.save()

        if coupon.send_notification:

            send_discount_notification(
                coupon
            )

class CouponDetailView(
    generics.RetrieveUpdateDestroyAPIView
):

    queryset = Coupon.objects.all()

    serializer_class = CouponSerializer

    permission_classes = [
        IsAuthenticated
    ]
    
class CouponDashboardView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        user = request.user

        qs = Coupon.objects.all()

        if user.role == "manager":

            qs = qs.filter(
                shop=user.manager_profile.shop
            )

        now = timezone.now()

        return Response({

            "summary":{

                "total":qs.count(),

                "active":qs.filter(
                    status="active",
                    start_date__lte=now,
                    end_date__gte=now
                ).count(),

                "expired":qs.filter(
                    end_date__lt=now
                ).count(),

                "inactive":qs.filter(
                    status="inactive"
                ).count(),

            },

            "latest":CouponSerializer(
                qs.order_by(
                    "-created_at"
                )[:10],
                many=True,
                context={
                    "request":request
                }
            ).data

        })
        
import random
import string


class BulkCouponGeneratorView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def post(self, request):

        quantity = int(
            request.data.get(
                "quantity",
                100
            )
        )

        prefix = request.data.get(
            "prefix",
            "RW"
        )

        created = []

        serializer = CouponSerializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        validated = serializer.validated_data

        for _ in range(quantity):

            code = (

                prefix +

                "".join(

                    random.choices(

                        string.ascii_uppercase +

                        string.digits,

                        k=8

                    )

                )

            )

            coupon = Coupon.objects.create(

                code=code,

                **validated

            )

            created.append(
                coupon.code
            )

        return Response({

            "success":True,

            "generated":len(created),

            "codes":created

        })
        
        

