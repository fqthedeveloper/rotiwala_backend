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
        
        
class MaintenanceCreateView(
    generics.CreateAPIView
):

    serializer_class = (
        MaintenanceExpenseSerializer
    )

    queryset = (
        MaintenanceExpense.objects.all()
    )

    def perform_create(
        self,
        serializer
    ):

        serializer.save(
            created_by=self.request.user
        )