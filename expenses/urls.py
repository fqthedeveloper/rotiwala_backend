# expenses/urls.py
from django.urls import path
from .views import *

urlpatterns = [
    # Existing
    path("categories/", ExpenseCategoryListView.as_view(), name="expense-categories"),
    path("category/<int:category_id>/items/", ExpenseMasterItemListView.as_view(), name="expense-master-items"),
    path("create/", CreateExpenseEntryView.as_view(), name="create-expense"),
    path("maintenance/create/", MaintenanceCreateView.as_view(), name="create-maintenance"),

    # New CRUD & reports
    path("", ExpenseListView.as_view(), name="expense-list"),
    path("<int:pk>/", ExpenseDetailView.as_view(), name="expense-detail"),
    path("maintenance/", MaintenanceExpenseListView.as_view(), name="maintenance-list"),
    path("maintenance/<int:pk>/", MaintenanceExpenseDetailView.as_view(), name="maintenance-detail"),
    path("report/", ExpenseReportView.as_view(), name="expense-report"),
]