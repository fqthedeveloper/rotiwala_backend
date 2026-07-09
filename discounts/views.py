from decimal import Decimal
from django.db.models import Q, Sum
from django.utils import timezone

from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Discount, DiscountUsage
from .serializers import DiscountSerializer

# ------------------------------------------------------------
#  LIST & CREATE (GET /api/discounts/ , POST /api/discounts/)
# ------------------------------------------------------------
class DiscountListCreateView(generics.ListCreateAPIView):
    serializer_class = DiscountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = Discount.objects.all()

        # Managers can only see discounts for their shop
        if user.role == "manager":
            qs = qs.filter(shop=user.manager_profile.shop)

        # Optional filtering via query params
        shop = self.request.GET.get("shop")
        if shop:
            # Include discounts for the shop OR global discounts (shop is null)
            qs = qs.filter(Q(shop_id=shop) | Q(shop__isnull=True))

        apply_on = self.request.GET.get("apply_on")
        if apply_on:
            qs = qs.filter(apply_on=apply_on)

        is_active = self.request.GET.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")

        search = self.request.GET.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )

        return qs.order_by("-created_at")

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == "manager":
            serializer.save(shop=user.manager_profile.shop)
        else:
            serializer.save()

# ------------------------------------------------------------
#  DETAIL (GET/PATCH/DELETE /api/discounts/<id>/)
# ------------------------------------------------------------
class DiscountDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Discount.objects.all()
    serializer_class = DiscountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.role == "manager":
            qs = qs.filter(shop=user.manager_profile.shop)
        return qs

# ------------------------------------------------------------
#  DASHBOARD (GET /api/discounts/dashboard/)
# ------------------------------------------------------------
class DiscountDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if user.role == "super_admin":
            discounts = Discount.objects.all()
        elif user.role == "manager":
            discounts = Discount.objects.filter(shop=user.manager_profile.shop)
        else:
            return Response({"detail": "Permission denied."}, status=403)

        now = timezone.now()
        active = discounts.filter(is_active=True, start_date__lte=now, end_date__gte=now)
        upcoming = discounts.filter(is_active=True, start_date__gt=now)
        expired = discounts.filter(end_date__lt=now)
        featured = discounts.filter(featured=True).order_by("display_order")[:10]
        latest = discounts.order_by("-created_at")[:10]

        serializer = DiscountSerializer(latest, many=True, context={"request": request})
        featured_serializer = DiscountSerializer(featured, many=True, context={"request": request})

        total_saved = DiscountUsage.objects.aggregate(total=Sum("discount_amount"))["total"] or 0
        total_usage = DiscountUsage.objects.count()

        return Response({
            "summary": {
                "total_discounts": discounts.count(),
                "active": active.count(),
                "upcoming": upcoming.count(),
                "expired": expired.count(),
                "featured": featured.count(),
                "times_used": total_usage,
                "total_discount_given": total_saved,
            },
            "featured": featured_serializer.data,
            "latest": serializer.data,
        })