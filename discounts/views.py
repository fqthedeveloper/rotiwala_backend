from decimal import Decimal
from django.db.models import Q, Sum
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Discount, DiscountUsage
from .serializers import DiscountSerializer

from accounts.models import User  # your custom user model
from discounts.models import DiscountUsage
from discounts.coupon_models import CouponUsage
from shops.models import Shop
from django.db.models import Sum, Count, Q, F
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from .serializers_coupon import UsageSummarySerializer, UsageListSerializer
from django.core.paginator import Paginator
from rest_framework.permissions import BasePermission


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
        


class AnalyticsAccessPermission(BasePermission):
    """
    Allows access to:
    - super_admin: view all shops
    - manager: view only their assigned shop
    """
    def has_permission(self, request, view):
        user = request.user
        # Must be authenticated
        if not user or not user.is_authenticated:
            return False
        # Allow if super_admin or manager
        return user.role in ['super_admin', 'manager']

    def has_object_permission(self, request, view, obj):
        # Not used for list views, but we can implement if needed
        return True


class UsageSummaryView(APIView):
    """
    GET /api/analytics/usage-summary/
    Query params: shop, start_date, end_date, group_by
    Returns aggregated usage data per date.
    Super_admin can see all; manager sees only their shop.
    """
    permission_classes = [AnalyticsAccessPermission]

    def get(self, request):
        user = request.user
        # Determine which shops to include
        if user.role == 'super_admin':
            # Can filter by shop param, otherwise all
            shop_id = request.query_params.get('shop')
            if shop_id:
                shop_filter = {'shop_id': shop_id}
            else:
                shop_filter = {}
        else:  # manager
            # Only their own shop
            if hasattr(user, 'manager_profile') and user.manager_profile.shop:
                shop_filter = {'shop': user.manager_profile.shop}
            else:
                return Response(
                    {"detail": "Manager has no assigned shop."},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Parse other filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        group_by = request.query_params.get('group_by', 'day')

        # Base querysets with filters
        discount_qs = DiscountUsage.objects.filter(**shop_filter)
        coupon_qs = CouponUsage.objects.filter(**shop_filter)

        if start_date:
            discount_qs = discount_qs.filter(created_at__date__gte=start_date)
            coupon_qs = coupon_qs.filter(created_at__date__gte=start_date)
        if end_date:
            discount_qs = discount_qs.filter(created_at__date__lte=end_date)
            coupon_qs = coupon_qs.filter(created_at__date__lte=end_date)

        # Truncation function
        trunc_func = {
            'day': TruncDay,
            'week': TruncWeek,
            'month': TruncMonth,
        }.get(group_by, TruncDay)

        # Aggregate discount usage
        discount_agg = (
            discount_qs
            .annotate(date=trunc_func('created_at'))
            .values('date')
            .annotate(count=Count('id'), total=Sum('discount_amount'))
            .order_by('date')
        )

        # Aggregate coupon usage
        coupon_agg = (
            coupon_qs
            .annotate(date=trunc_func('created_at'))
            .values('date')
            .annotate(count=Count('id'), total=Sum('discount_amount'))
            .order_by('date')
        )

        # Combine results by date
        combined = {}
        for item in discount_agg:
            date_str = item['date'].date().isoformat()
            combined[date_str] = {
                'date': date_str,
                'discount_count': item['count'],
                'discount_total': item['total'] or Decimal('0.00'),
                'coupon_count': 0,
                'coupon_total': Decimal('0.00'),
            }
        for item in coupon_agg:
            date_str = item['date'].date().isoformat()
            if date_str in combined:
                combined[date_str]['coupon_count'] = item['count']
                combined[date_str]['coupon_total'] = item['total'] or Decimal('0.00')
            else:
                combined[date_str] = {
                    'date': date_str,
                    'discount_count': 0,
                    'discount_total': Decimal('0.00'),
                    'coupon_count': item['count'],
                    'coupon_total': item['total'] or Decimal('0.00'),
                }

        # Build response
        result = []
        for date_str, data in sorted(combined.items()):
            result.append({
                'date': date_str,
                'total_usage_count': data['discount_count'] + data['coupon_count'],
                'total_discount_amount': data['discount_total'] + data['coupon_total'],
                'discount_usage_count': data['discount_count'],
                'coupon_usage_count': data['coupon_count'],
                'discount_total_amount': data['discount_total'],
                'coupon_total_amount': data['coupon_total'],
            })

        overall = {
            'total_usage_count': sum(r['total_usage_count'] for r in result),
            'total_discount_amount': sum(r['total_discount_amount'] for r in result),
            'discount_usage_count': sum(r['discount_usage_count'] for r in result),
            'coupon_usage_count': sum(r['coupon_usage_count'] for r in result),
            'discount_total_amount': sum(r['discount_total_amount'] for r in result),
            'coupon_total_amount': sum(r['coupon_total_amount'] for r in result),
        }

        return Response({
            'overall': overall,
            'data': result,
        })


class UsageListView(generics.ListAPIView):
    """
    GET /api/analytics/usage-list/
    Returns paginated list of usage records.
    Super_admin can see all; manager sees only their shop.
    """
    permission_classes = [AnalyticsAccessPermission]
    serializer_class = UsageListSerializer

    def get_queryset(self):
        user = self.request.user
        # Determine shop filter
        if user.role == 'super_admin':
            shop_id = self.request.query_params.get('shop')
            if shop_id:
                shop_filter = {'shop_id': shop_id}
            else:
                shop_filter = {}
        else:  # manager
            if hasattr(user, 'manager_profile') and user.manager_profile.shop:
                shop_filter = {'shop': user.manager_profile.shop}
            else:
                return []  # No shop assigned

        # Base querysets
        discount_qs = DiscountUsage.objects.filter(**shop_filter).select_related('shop', 'order', 'customer', 'discount')
        coupon_qs = CouponUsage.objects.filter(**shop_filter).select_related('shop', 'order', 'customer', 'coupon')

        # Apply extra filters
        start_date = self.request.query_params.get('start_date')
        if start_date:
            discount_qs = discount_qs.filter(created_at__date__gte=start_date)
            coupon_qs = coupon_qs.filter(created_at__date__gte=start_date)

        end_date = self.request.query_params.get('end_date')
        if end_date:
            discount_qs = discount_qs.filter(created_at__date__lte=end_date)
            coupon_qs = coupon_qs.filter(created_at__date__lte=end_date)

        type_filter = self.request.query_params.get('type')
        if type_filter == 'discount':
            coupon_qs = coupon_qs.none()
        elif type_filter == 'coupon':
            discount_qs = discount_qs.none()

        order_type = self.request.query_params.get('order_type')
        if order_type:
            discount_qs = discount_qs.filter(order_type=order_type)
            coupon_qs = coupon_qs.filter(order_type=order_type)

        search = self.request.query_params.get('search')
        if search:
            discount_qs = discount_qs.filter(
                Q(order__order_number__icontains=search) |
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search)
            )
            coupon_qs = coupon_qs.filter(
                Q(order__order_number__icontains=search) |
                Q(customer__first_name__icontains=search) |
                Q(customer__last_name__icontains=search)
            )

        # Convert to list of dicts
        discount_list = []
        for obj in discount_qs:
            discount_list.append({
                'id': obj.id,
                'type': 'discount',
                'shop': obj.shop,
                'shop_name': obj.shop.name,
                'order': obj.order,
                'order_number': obj.order.order_number,
                'customer': obj.customer,
                'customer_name': obj.customer.get_full_name() or obj.customer.email,
                'order_type': obj.order_type,
                'original_amount': obj.original_amount,
                'discount_amount': obj.discount_amount,
                'final_amount': obj.final_amount,
                'created_at': obj.created_at,
                'discount_name': obj.discount.name,
                'coupon_name': None,
            })

        coupon_list = []
        for obj in coupon_qs:
            coupon_list.append({
                'id': obj.id,
                'type': 'coupon',
                'shop': obj.shop,
                'shop_name': obj.shop.name,
                'order': obj.order,
                'order_number': obj.order.order_number,
                'customer': obj.customer,
                'customer_name': obj.customer.get_full_name() or obj.customer.email,
                'order_type': obj.order_type,
                'original_amount': obj.original_amount,
                'discount_amount': obj.discount_amount,
                'final_amount': obj.final_amount,
                'created_at': obj.created_at,
                'discount_name': None,
                'coupon_name': obj.coupon.name,
            })

        combined = discount_list + coupon_list
        combined.sort(key=lambda x: x['created_at'], reverse=True)
        return combined

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        paginator = Paginator(queryset, page_size)
        page_obj = paginator.get_page(page)

        serializer = self.get_serializer(page_obj, many=True)
        return Response({
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': page,
            'results': serializer.data,
        })