from rest_framework import serializers
from .models import (
    ExpenseCategory,
    ExpenseMasterItem,
    ExpenseEntry,
    ExpenseItemEntry,
    MaintenanceExpense,
    Staff,
    StaffSalaryRecord,
    Vendor, RawMaterialExpense
)


class ExpenseCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseCategory
        fields = "__all__"


class ExpenseMasterItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseMasterItem
        fields = "__all__"


class ExpenseItemEntrySerializer(serializers.ModelSerializer):
    item_name = serializers.ReadOnlyField()

    class Meta:
        model = ExpenseItemEntry
        fields = "__all__"


class ExpenseEntrySerializer(serializers.ModelSerializer):
    category = ExpenseCategorySerializer(read_only=True)
    expense_items = ExpenseItemEntrySerializer(many=True, read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)

    class Meta:
        model = ExpenseEntry
        fields = "__all__"
        depth = 1


class MaintenanceExpenseSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)

    class Meta:
        model = MaintenanceExpense
        fields = [
            'id', 'shop', 'shop_name', 'title', 'description', 'amount',
            'maintenance_date', 'payment_method', 'utr_number',
            'created_by', 'created_by_name', 'created_at',
        ]
        extra_kwargs = {
            'shop': {'required': False},  # Handled manually in view
        }


class StaffSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    total_paid = serializers.SerializerMethodField()
    remaining_salary = serializers.SerializerMethodField()
    has_kitchen_login = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Staff
        fields = "__all__"
        extra_kwargs = {
            'shop': {'required': False},
        }

    def get_total_paid(self, obj):
        from django.db.models import Sum
        total = obj.salary_records.aggregate(total=Sum('amount'))['total']
        return total or 0

    def get_remaining_salary(self, obj):
        from django.db.models import Sum
        total = obj.salary_records.aggregate(total=Sum('amount'))['total'] or 0
        return obj.monthly_salary - total

    def get_has_kitchen_login(self, obj):
        return bool(obj.user and hasattr(obj.user, 'preparing_staff_profile'))

    def create(self, validated_data):
        validated_data.pop('password', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('password', None)
        return super().update(instance, validated_data)


class StaffSalaryRecordSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source='staff.name', read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)
    payment_method_display = serializers.CharField(source='get_payment_method_display', read_only=True)
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)

    class Meta:
        model = StaffSalaryRecord
        fields = "__all__"


class StaffSalaryCreateSerializer(serializers.Serializer):
    staff_id = serializers.IntegerField()
    payment_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=['CASH', 'ONLINE'])
    utr_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    payment_type = serializers.ChoiceField(
        choices=['MONTHLY', 'ADVANCE', 'BONUS', 'DEDUCTION', 'EMERGENCY'],
        default='MONTHLY'
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class StaffSalaryDetailSerializer(serializers.Serializer):
    staff = StaffSerializer()
    total_paid = serializers.DecimalField(max_digits=12, decimal_places=2)
    remaining = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthly_salary = serializers.DecimalField(max_digits=10, decimal_places=2)
    records = StaffSalaryRecordSerializer(many=True)




class VendorSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    class Meta:
        model = Vendor
        fields = "__all__"


class RawMaterialExpenseSerializer(serializers.ModelSerializer):
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    vendor_name = serializers.CharField(source='vendor.name', read_only=True, default=None)
    item_name = serializers.CharField(source='item.name', read_only=True, default=None)
    unit_display = serializers.CharField(source='get_unit_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True, default=None)

    class Meta:
        model = RawMaterialExpense
        fields = [
            'id', 'shop', 'shop_name', 'vendor', 'vendor_name', 'item', 'item_name',
            'custom_item_name', 'quantity', 'unit', 'unit_display', 'unit_price',
            'amount', 'note', 'payment_method', 'utr_number', 'expense_date',
            'created_by', 'created_by_name', 'created_at', 'updated_at', 'expense_entry',
        ]
        extra_kwargs = {
            'shop': {'required': False},  # Handled in view
        }