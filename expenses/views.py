from rest_framework import generics
from .models import ExpenseCategory, MaintenanceExpense
from .serializers import ExpenseCategorySerializer
from .models import ExpenseMasterItem
from .serializers import ExpenseMasterItemSerializer, MaintenanceExpenseSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from decimal import Decimal

from .models import (
    ExpenseEntry,
    ExpenseItemEntry,
    ExpenseCategory
)
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import ExpenseEntry, ExpenseItemEntry, ExpenseCategory, MaintenanceExpense
from .serializers import ExpenseEntrySerializer, MaintenanceExpenseSerializer, ExpenseCategorySerializer
from accounts.permissions import IsSuperAdmin 
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from shops.models import Shop  # adjust import to your actual Shop model



class ExpenseCategoryListView(
    generics.ListAPIView
):

    queryset = ExpenseCategory.objects.filter(
        is_active=True
    )

    serializer_class = ExpenseCategorySerializer
    

class ExpenseMasterItemListView(
    generics.ListAPIView
):

    serializer_class = ExpenseMasterItemSerializer

    def get_queryset(self):

        category_id = self.kwargs["category_id"]

        return ExpenseMasterItem.objects.filter(
            category_id=category_id,
            is_active=True
        )
        


class CreateExpenseEntryView(APIView):

    def post(self, request):

        category_id = request.data.get(
            "category_id"
        )

        shop_id = request.data.get(
            "shop_id"
        )

        expense = ExpenseEntry.objects.create(
            shop_id=shop_id,
            category_id=category_id,
            created_by=request.user,
            expense_date=request.data.get(
                "expense_date"
            )
        )

        total = Decimal("0")

        items = request.data.get(
            "items",
            []
        )

        for item in items:

            amount = Decimal(
                str(item["amount"])
            )

            ExpenseItemEntry.objects.create(
                expense=expense,
                master_item_id=item.get(
                    "master_item"
                ),
                custom_item_name=item.get(
                    "custom_item_name"
                ),
                quantity=item.get(
                    "quantity"
                ),
                amount=amount,
                note=item.get(
                    "note"
                )
            )

            total += amount

        expense.total_amount = total

        expense.save()

        return Response({
            "message": "Expense Saved",
            "expense_id": expense.id,
            "total": total
        })
        
        
class MaintenanceCreateView(generics.CreateAPIView):
    serializer_class = MaintenanceExpenseSerializer
    queryset = MaintenanceExpense.objects.all()
    permission_classes = [IsAuthenticated]   # or combine (IsSuperAdmin | IsManager)

    def perform_create(self, serializer):
        user = self.request.user

        if user.role == 'manager':
            # Use the manager's own shop
            try:
                shop = user.manager_profile.shop
            except AttributeError:
                raise ValidationError({"detail": "Manager profile has no shop."})
            # Force the shop; ignore any value the client might have sent
            serializer.save(shop=shop, created_by=user)

        elif user.role == 'super_admin':
            shop_id = self.request.data.get('shop')
            if not shop_id:
                # Optional: assign the first shop as a fallback
                shop = Shop.objects.first()
                if not shop:
                    raise ValidationError({"detail": "No shops exist."})
            else:
                shop = get_object_or_404(Shop, id=shop_id)
            serializer.save(shop=shop, created_by=user)

        else:
            raise ValidationError({"detail": "You are not allowed to create maintenance expenses."})
        


class ExpenseListView(generics.ListAPIView):
    """
    List all expenses with filters (super admin sees all, manager sees only his shop)
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ExpenseEntrySerializer
    pagination_class = PageNumberPagination
    pagination_class.page_size = 20
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'shop', 'expense_date']
    search_fields = ['shop__name', 'category__name', 'notes']
    ordering_fields = ['expense_date', 'total_amount']
    ordering = ['-expense_date']

    def get_queryset(self):
        user = self.request.user
        queryset = ExpenseEntry.objects.select_related('shop', 'category', 'created_by')
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                queryset = queryset.filter(shop=shop)
            except:
                queryset = queryset.none()
        # Super admin sees all
        return queryset


class ExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ExpenseEntrySerializer
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        queryset = ExpenseEntry.objects.select_related('shop', 'category', 'created_by')
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                queryset = queryset.filter(shop=shop)
            except:
                queryset = queryset.none()
        return queryset


class MaintenanceExpenseListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MaintenanceExpenseSerializer
    pagination_class = PageNumberPagination
    pagination_class.page_size = 20
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['shop', 'maintenance_date']
    search_fields = ['title', 'description']
    ordering_fields = ['maintenance_date', 'amount']
    ordering = ['-maintenance_date']

    def get_queryset(self):
        user = self.request.user
        queryset = MaintenanceExpense.objects.select_related('shop', 'created_by')
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                queryset = queryset.filter(shop=shop)
            except:
                queryset = queryset.none()
        return queryset


class MaintenanceExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = MaintenanceExpenseSerializer
    lookup_field = 'pk'

    def get_queryset(self):
        user = self.request.user
        queryset = MaintenanceExpense.objects.select_related('shop', 'created_by')
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                queryset = queryset.filter(shop=shop)
            except:
                queryset = queryset.none()
        return queryset


class ExpenseReportView(APIView):
    """
    Aggregate report: total expenses by category, shop, date range
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        # Base queryset
        queryset = ExpenseEntry.objects.all()
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                queryset = queryset.filter(shop=shop)
            except:
                queryset = queryset.none()

        # Filters
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(expense_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(expense_date__lte=end_date)

        shop_id = request.query_params.get('shop_id')
        if shop_id:
            queryset = queryset.filter(shop_id=shop_id)

        # Aggregations
        total_expenses = queryset.aggregate(total=Sum('total_amount'))['total'] or 0

        # By category
        by_category = (
            queryset.values('category__name')
            .annotate(total=Sum('total_amount'))
            .order_by('-total')
        )

        # By shop (super admin only)
        by_shop = None
        if user.role == 'super_admin':
            by_shop = (
                queryset.values('shop__name')
                .annotate(total=Sum('total_amount'))
                .order_by('-total')
            )

        # Monthly trend (last 6 months)
        from django.db.models.functions import TruncMonth
        monthly_trend = (
            queryset
            .annotate(month=TruncMonth('expense_date'))
            .values('month')
            .annotate(total=Sum('total_amount'))
            .order_by('month')
        )

        return Response({
            'total_expenses': total_expenses,
            'by_category': list(by_category),
            'by_shop': list(by_shop) if by_shop else None,
            'monthly_trend': list(monthly_trend),
        })