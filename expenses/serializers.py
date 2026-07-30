from rest_framework import serializers

from .models import (
    ExpenseCategory,
    ExpenseMasterItem,
    ExpenseEntry,
    ExpenseItemEntry,
    MaintenanceExpense
)


class ExpenseCategorySerializer(
    serializers.ModelSerializer
):

    class Meta:
        model = ExpenseCategory
        fields = "__all__"


class ExpenseMasterItemSerializer(
    serializers.ModelSerializer
):

    class Meta:
        model = ExpenseMasterItem
        fields = "__all__"


class ExpenseItemEntrySerializer(
    serializers.ModelSerializer
):

    item_name = serializers.ReadOnlyField()

    class Meta:
        model = ExpenseItemEntry
        fields = "__all__"


class ExpenseEntrySerializer(
    serializers.ModelSerializer
):
    category = ExpenseCategorySerializer(
        read_only=True
    )
    expense_items = ExpenseItemEntrySerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = ExpenseEntry
        fields = "__all__"
        deepth = 2


class MaintenanceExpenseSerializer(
    serializers.ModelSerializer
):

    class Meta:
        model = MaintenanceExpense
        fields = "__all__"
        extra_kwargs = {
            'shop': {'required': False},   # <-- add this
        }