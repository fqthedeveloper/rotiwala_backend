from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.db.models import Sum
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from datetime import datetime
from decimal import Decimal
from accounts.permissions import IsSuperAdmin
from shops.models import Shop
from .models import (
    ExpenseCategory,
    ExpenseMasterItem,
    ExpenseEntry,
    ExpenseItemEntry,
    MaintenanceExpense,
    Staff,
    StaffSalaryRecord,
    RawMaterialExpense,
    Vendor
)
from .serializers import (
    ExpenseCategorySerializer,
    ExpenseMasterItemSerializer,
    ExpenseEntrySerializer,
    MaintenanceExpenseSerializer,
    StaffSerializer,
    StaffSalaryCreateSerializer,
    StaffSalaryRecordSerializer,   # <-- ADD THIS
    StaffSalaryDetailSerializer,
    VendorSerializer,
    RawMaterialExpenseSerializer
)


# -------------------- MASTER ITEMS (Super Admin) --------------------

class ExpenseCategoryListView(generics.ListAPIView):
    """List all active categories"""
    permission_classes = [IsAuthenticated]
    queryset = ExpenseCategory.objects.filter(is_active=True)
    serializer_class = ExpenseCategorySerializer


class ExpenseMasterItemListView(generics.ListAPIView):
    """List master items for a specific category (e.g., Raw Materials)"""
    permission_classes = [IsAuthenticated]
    serializer_class = ExpenseMasterItemSerializer

    def get_queryset(self):
        category_id = self.kwargs["category_id"]
        return ExpenseMasterItem.objects.filter(category_id=category_id, is_active=True)


class ExpenseMasterItemCreateView(generics.CreateAPIView):
    """Super Admin ONLY: Add a new Raw Material name (e.g., 'Atta')"""
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = ExpenseMasterItemSerializer
    queryset = ExpenseMasterItem.objects.all()


# -------------------- EXPENSE ENTRIES (Raw + Salary) --------------------

class CreateExpenseEntryView(APIView):
    """
    Create a new expense entry.
    - Manager: Shop is auto-assigned. Cannot pass shop_id.
    - Super Admin: Must pass shop_id.
    Supports multiple items in a single entry.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        category_id = request.data.get("category_id")
        notes = request.data.get("notes", "")

        # --- 1. Shop Validation & Assignment ---
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
            except AttributeError:
                return Response({"detail": "Manager profile has no shop assigned."},
                                status=status.HTTP_400_BAD_REQUEST)
        elif user.role == 'super_admin':
            shop_id = request.data.get("shop_id")
            if not shop_id:
                return Response({"detail": "Shop ID is required for Super Admin."},
                                status=status.HTTP_400_BAD_REQUEST)
            shop = get_object_or_404(Shop, id=shop_id)
        else:
            return Response({"detail": "You are not allowed to create expenses."},
                            status=status.HTTP_403_FORBIDDEN)

        # --- 2. Validate Category ---
        category = get_object_or_404(ExpenseCategory, id=category_id, is_active=True)

        # --- 3. Get DateTime (use provided or default to now) ---
        entry_datetime = request.data.get("entry_datetime")
        if entry_datetime:
            # If frontend sends a string, DRF's parser handles it, but we parse safely.
            # For simplicity, we assume it's a valid ISO string or None.
            pass
        else:
            entry_datetime = timezone.now()

        # --- 4. Create Header ---
        expense = ExpenseEntry.objects.create(
            shop=shop,
            category=category,
            created_by=user,
            entry_datetime=entry_datetime,
            notes=notes
        )

        # --- 5. Create Line Items & Calculate Total ---
        total = Decimal("0")
        items = request.data.get("items", [])

        if not items:
            return Response({"detail": "At least one item is required."},
                            status=status.HTTP_400_BAD_REQUEST)

        for item in items:
            amount = Decimal(str(item["amount"]))

            # For Salary: custom_item_name is required (Staff Name)
            # For Raw: master_item is required, custom_item_name can be empty
            # We allow flexibility here.
            master_item_id = item.get("master_item")
            custom_name = item.get("custom_item_name", "")

            # Basic validation: either master_item or custom_name must be provided
            if not master_item_id and not custom_name:
                raise ValidationError({"detail": "Each item must have a master_item or a custom_item_name."})

            ExpenseItemEntry.objects.create(
                expense=expense,
                master_item_id=master_item_id,
                custom_item_name=custom_name,
                quantity=item.get("quantity"),  # Can be None for Salary
                amount=amount,
                note=item.get("note", "")
            )
            total += amount

        expense.total_amount = total
        expense.save()

        return Response({
            "message": "Expense saved successfully.",
            "expense_id": expense.id,
            "total": total,
            "entry_datetime": expense.entry_datetime
        }, status=status.HTTP_201_CREATED)


class ExpenseListView(generics.ListAPIView):
    """
    List all expenses.
    - Manager: Only sees their shop.
    - Super Admin: Sees all shops.
    Filters: category, shop, entry_datetime (date range).
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ExpenseEntrySerializer
    pagination_class = PageNumberPagination
    pagination_class.page_size = 20
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'shop', 'entry_datetime']
    search_fields = ['shop__name', 'category__name', 'notes']
    ordering_fields = ['entry_datetime', 'total_amount']
    ordering = ['-entry_datetime']

    def get_queryset(self):
        user = self.request.user
        queryset = ExpenseEntry.objects.select_related('shop', 'category', 'created_by')

        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                queryset = queryset.filter(shop=shop)
            except AttributeError:
                queryset = ExpenseEntry.objects.none()
        # Super admin sees all

        # Handle date range filters manually if needed, but DjangoFilterBackend handles field lookups
        # e.g., ?entry_datetime__gte=2026-08-01&entry_datetime__lte=2026-08-07
        return queryset


class ExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, Update, or Delete an expense.
    - Manager: Only can modify their shop's expenses.
    - Super Admin: Can modify any.
    """
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
            except AttributeError:
                queryset = ExpenseEntry.objects.none()
        return queryset


# -------------------- MAINTENANCE EXPENSES --------------------

class MaintenanceCreateView(generics.CreateAPIView):
    """
    Create a maintenance expense.
    - Manager: Shop auto-assigned.
    - Super Admin: Must pass shop_id.
    """
    serializer_class = MaintenanceExpenseSerializer
    queryset = MaintenanceExpense.objects.all()
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        user = self.request.user

        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
            except AttributeError:
                raise ValidationError({"detail": "Manager profile has no shop."})
            serializer.save(shop=shop, created_by=user)

        elif user.role == 'super_admin':
            shop_id = self.request.data.get('shop')
            if not shop_id:
                shop = Shop.objects.first()
                if not shop:
                    raise ValidationError({"detail": "No shops exist."})
            else:
                shop = get_object_or_404(Shop, id=shop_id)
            serializer.save(shop=shop, created_by=user)

        else:
            raise ValidationError({"detail": "You are not allowed to create maintenance expenses."})


class MaintenanceExpenseListView(generics.ListAPIView):
    """
    List maintenance expenses.
    - Manager: Only sees their shop.
    - Super Admin: Sees all.
    """
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
            except AttributeError:
                queryset = MaintenanceExpense.objects.none()
        return queryset


class MaintenanceExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Retrieve, Update, or Delete a maintenance expense.
    - Manager: Only their shop.
    - Super Admin: Any.
    """
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
            except AttributeError:
                queryset = MaintenanceExpense.objects.none()
        return queryset


# -------------------- REPORTS & ANALYTICS --------------------

class ExpenseReportView(APIView):
    """
    Generate aggregate reports.
    - Manager: Only their shop.
    - Super Admin: All shops (or filtered by shop_id).
    Filters: start_date, end_date, shop_id.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        queryset = ExpenseEntry.objects.all()

        # --- Shop Filtering ---
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                queryset = queryset.filter(shop=shop)
            except AttributeError:
                queryset = ExpenseEntry.objects.none()
        elif user.role == 'super_admin':
            shop_id = request.query_params.get('shop_id')
            if shop_id:
                queryset = queryset.filter(shop_id=shop_id)

        # --- Date Filters ---
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(entry_datetime__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(entry_datetime__date__lte=end_date)

        # --- Aggregations ---
        total_expenses = queryset.aggregate(total=Sum('total_amount'))['total'] or 0

        # By Category
        by_category = (
            queryset.values('category__name')
            .annotate(total=Sum('total_amount'))
            .order_by('-total')
        )

        # By Shop (Super Admin only)
        by_shop = None
        if user.role == 'super_admin':
            by_shop = (
                queryset.values('shop__name')
                .annotate(total=Sum('total_amount'))
                .order_by('-total')
            )

        # Monthly Trend (Last 6 months)
        monthly_trend = (
            queryset
            .annotate(month=TruncMonth('entry_datetime'))
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


# expenses/views.py – add these new classes

class ExpenseCategoryCreateView(generics.CreateAPIView):
    """Super Admin only: Create a new expense category."""
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = ExpenseCategorySerializer
    queryset = ExpenseCategory.objects.all()


class ExpenseCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Super Admin only: Retrieve, update, or delete a category."""
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = ExpenseCategorySerializer
    queryset = ExpenseCategory.objects.all()
    lookup_field = 'pk'



class ExpenseMasterItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    Super Admin only: Retrieve, update, or delete a master item (e.g., Atta).
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = ExpenseMasterItemSerializer
    queryset = ExpenseMasterItem.objects.all()
    lookup_field = 'pk'


# -------------------- STAFF CRUD --------------------

class StaffListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StaffSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                return Staff.objects.filter(shop=shop)
            except:
                return Staff.objects.none()
        return Staff.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'manager':
            shop = user.manager_profile.shop
            staff = serializer.save(shop=shop)
        else:
            shop_id = self.request.data.get('shop')
            if not shop_id:
                raise ValidationError({"detail": "shop is required for super admin"})
            shop = get_object_or_404(Shop, id=shop_id)
            staff = serializer.save(shop=shop)

        # Synchronize/Create kitchen preparing staff login
        phone = (staff.phone or '').strip()
        if phone:
            from accounts.models import User as AccountUser, PreparingStaffProfile
            raw_password = self.request.data.get('password') or phone
            account_user = AccountUser.objects.filter(phone=phone).first()
            if not account_user:
                account_user = AccountUser.objects.create_user(
                    username=phone,
                    phone=phone,
                    password=raw_password,
                    role='preparing_staff',
                    first_name=staff.name.split(' ')[0] if staff.name else '',
                    last_name=' '.join(staff.name.split(' ')[1:]) if len(staff.name.split(' ')) > 1 else '',
                    is_active=staff.is_active
                )
            else:
                if raw_password and raw_password != phone:
                    account_user.set_password(raw_password)
                    account_user.save()

            profile, _ = PreparingStaffProfile.objects.get_or_create(user=account_user)
            profile.shop = staff.shop
            profile.full_name = staff.name
            profile.phone = phone
            profile.is_active = staff.is_active
            profile.save()

            if staff.user != account_user:
                staff.user = account_user
                staff.save(update_fields=['user'])


class StaffDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = StaffSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                return Staff.objects.filter(shop=shop)
            except:
                return Staff.objects.none()
        return Staff.objects.all()

    def perform_update(self, serializer):
        staff = serializer.save()
        phone = (staff.phone or '').strip()
        raw_password = self.request.data.get('password')
        from accounts.models import User as AccountUser, PreparingStaffProfile

        account_user = staff.user
        if not account_user and phone:
            account_user = AccountUser.objects.filter(phone=phone).first()
            if not account_user:
                account_user = AccountUser.objects.create_user(
                    username=phone,
                    phone=phone,
                    password=raw_password or phone,
                    role='preparing_staff',
                    first_name=staff.name.split(' ')[0] if staff.name else '',
                    last_name=' '.join(staff.name.split(' ')[1:]) if len(staff.name.split(' ')) > 1 else '',
                    is_active=staff.is_active
                )
            staff.user = account_user
            staff.save(update_fields=['user'])

        if account_user:
            account_user.first_name = staff.name.split(' ')[0] if staff.name else ''
            account_user.last_name = ' '.join(staff.name.split(' ')[1:]) if len(staff.name.split(' ')) > 1 else ''
            account_user.is_active = staff.is_active
            if phone and account_user.phone != phone:
                account_user.phone = phone
            if raw_password:
                account_user.set_password(raw_password)
            account_user.save()

            profile, _ = PreparingStaffProfile.objects.get_or_create(user=account_user)
            profile.shop = staff.shop
            profile.full_name = staff.name
            profile.phone = phone or profile.phone
            profile.is_active = staff.is_active
            profile.save()

    def perform_destroy(self, instance):
        user = instance.user
        instance.delete()
        if user and user.role == 'preparing_staff':
            try:
                if hasattr(user, 'preparing_staff_profile'):
                    user.preparing_staff_profile.delete()
                user.delete()
            except Exception:
                pass


# -------------------- STAFF SALARY (NEW & IMPROVED) --------------------

class AddStaffSalaryView(APIView):
    """Add staff salary/advance with payment method"""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = StaffSalaryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        staff_id = serializer.validated_data['staff_id']
        payment_date = serializer.validated_data['payment_date']
        amount = serializer.validated_data['amount']
        payment_method = serializer.validated_data['payment_method']
        utr_number = serializer.validated_data.get('utr_number', '')
        payment_type = serializer.validated_data.get('payment_type', 'MONTHLY')
        notes = serializer.validated_data.get('notes', '')

        staff = get_object_or_404(Staff, id=staff_id)

        user = request.user
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                if staff.shop != shop:
                    raise PermissionDenied("You can only add salary for your shop's staff.")
            except:
                raise PermissionDenied("Manager profile not found.")

        # Validate UTR for online payments
        if payment_method == 'ONLINE' and not utr_number:
            return Response(
                {"detail": "UTR number is required for online payments."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create category "Staff Salary"
        category, _ = ExpenseCategory.objects.get_or_create(
            name="Staff Salary",
            defaults={"is_active": True}
        )

        # Create expense entry
        expense = ExpenseEntry.objects.create(
            shop=staff.shop,
            category=category,
            created_by=user,
            entry_datetime=payment_date,
            total_amount=amount,
            notes=f"{payment_type} for {staff.name} - {payment_date.strftime('%d %B %Y')}"
        )

        # Create expense item entry
        ExpenseItemEntry.objects.create(
            expense=expense,
            custom_item_name=staff.name,
            quantity=None,
            amount=amount,
            note=notes or f"{payment_type} on {payment_date.strftime('%d %B %Y')}"
        )

        # Create staff salary record
        salary_record = StaffSalaryRecord.objects.create(
            staff=staff,
            shop=staff.shop,
            expense_entry=expense,
            amount=amount,
            payment_date=payment_date,
            payment_method=payment_method,
            utr_number=utr_number if payment_method == 'ONLINE' else None,
            notes=notes,
            payment_type=payment_type,
            created_by=user
        )

        return Response({
            "message": "Salary payment recorded successfully.",
            "salary_id": salary_record.id,
            "expense_id": expense.id,
            "amount": amount,
            "payment_method": payment_method,
            "utr_number": utr_number if payment_method == 'ONLINE' else None,
            "date": payment_date
        }, status=status.HTTP_201_CREATED)


class StaffSalaryDetailView(APIView):
    """Get complete staff salary details with history and balance"""
    permission_classes = [IsAuthenticated]

    def get(self, request, staff_id):
        staff = get_object_or_404(Staff, id=staff_id)

        # Check permissions
        user = request.user
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                if staff.shop != shop:
                    return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)
            except:
                return Response({"detail": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        # Get all salary records
        records = staff.salary_records.all().order_by('-payment_date', '-created_at')

        # Calculate totals
        total_paid = records.aggregate(total=Sum('amount'))['total'] or 0
        remaining = staff.monthly_salary - total_paid

        # Get monthly breakdown
        monthly_breakdown = (
            records
            .annotate(month=TruncMonth('payment_date'))
            .values('month')
            .annotate(total=Sum('amount'))
            .order_by('-month')
        )

        return Response({
            "staff": StaffSerializer(staff).data,
            "total_paid": total_paid,
            "remaining": remaining,
            "monthly_salary": staff.monthly_salary,
            "records": StaffSalaryRecordSerializer(records, many=True).data,
            "monthly_breakdown": list(monthly_breakdown),
        })


class StaffSalaryListView(APIView):
    """List all staff with salary summary"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user

        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                staff_list = Staff.objects.filter(shop=shop, is_active=True)
            except:
                return Response({"detail": "Manager profile not found."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            staff_list = Staff.objects.filter(is_active=True)

        result = []
        for staff in staff_list:
            total_paid = staff.salary_records.aggregate(total=Sum('amount'))['total'] or 0
            remaining = staff.monthly_salary - total_paid

            result.append({
                "id": staff.id,
                "name": staff.name,
                "phone": staff.phone,
                "shop": staff.shop.name,
                "monthly_salary": staff.monthly_salary,
                "total_paid": total_paid,
                "remaining": remaining,
                "is_active": staff.is_active,
            })

        return Response(result)


class StaffSalaryReportView(APIView):
    """Staff salary report with filters"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        queryset = StaffSalaryRecord.objects.select_related('staff', 'shop')

        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                queryset = queryset.filter(shop=shop)
            except:
                queryset = StaffSalaryRecord.objects.none()

        # Filters
        staff_id = request.query_params.get('staff_id')
        if staff_id:
            queryset = queryset.filter(staff_id=staff_id)

        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)

        payment_method = request.query_params.get('payment_method')
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)

        # Aggregations
        total_amount = queryset.aggregate(total=Sum('amount'))['total'] or 0

        by_staff = (
            queryset.values('staff__name')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        by_method = (
            queryset.values('payment_method')
            .annotate(total=Sum('amount'))
            .order_by('-total')
        )

        return Response({
            "total_amount": total_amount,
            "by_staff": list(by_staff),
            "by_method": list(by_method),
            "records": StaffSalaryRecordSerializer(queryset, many=True).data,
        })


class VendorListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                return Vendor.objects.filter(shop=shop, is_active=True)
            except:
                return Vendor.objects.none()
        return Vendor.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'manager':
            shop = user.manager_profile.shop
            serializer.save(shop=shop)
        else:
            shop_id = self.request.data.get('shop')
            if not shop_id:
                raise ValidationError({"detail": "shop is required for super admin"})
            shop = get_object_or_404(Shop, id=shop_id)
            serializer.save(shop=shop)


class VendorDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VendorSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                return Vendor.objects.filter(shop=shop)
            except:
                return Vendor.objects.none()
        return Vendor.objects.all()


class RawMaterialExpenseListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RawMaterialExpenseSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                return RawMaterialExpense.objects.filter(shop=shop)
            except:
                return RawMaterialExpense.objects.none()
        return RawMaterialExpense.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == 'manager':
            shop = user.manager_profile.shop
        else:
            shop_id = self.request.data.get('shop')
            if not shop_id:
                raise ValidationError({"detail": "shop is required for super admin"})
            shop = get_object_or_404(Shop, id=shop_id)
        serializer.save(shop=shop, created_by=user)


class RawMaterialExpenseDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RawMaterialExpenseSerializer

    def get_queryset(self):
        user = self.request.user
        if user.role == 'manager':
            try:
                shop = user.manager_profile.shop
                return RawMaterialExpense.objects.filter(shop=shop)
            except:
                return RawMaterialExpense.objects.none()
        return RawMaterialExpense.objects.all()