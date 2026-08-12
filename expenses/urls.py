from django.urls import path
from .views import *

urlpatterns = [
    # --- Master Data (Super Admin only for creation) ---
    path("categories/", ExpenseCategoryListView.as_view(), name="expense-categories"),
    path("category/<int:category_id>/items/", ExpenseMasterItemListView.as_view(), name="expense-master-items"),
    path("master-items/create/", ExpenseMasterItemCreateView.as_view(), name="create-master-item"),
    path("categories/", ExpenseCategoryListView.as_view(), name="expense-categories"),
    path("categories/create/", ExpenseCategoryCreateView.as_view(), name="create-expense-category"),
    path("categories/<int:pk>/", ExpenseCategoryDetailView.as_view(), name="expense-category-detail"),

    # --- Expense Entries (Raw & Salary) ---
    path("create/", CreateExpenseEntryView.as_view(), name="create-expense"),
    path("", ExpenseListView.as_view(), name="expense-list"),
    path("<int:pk>/", ExpenseDetailView.as_view(), name="expense-detail"),
    path("master-items/create/", ExpenseMasterItemCreateView.as_view(), name="create-master-item"),
    path("master-items/<int:pk>/", ExpenseMasterItemDetailView.as_view(), name="master-item-detail"),

    # --- Maintenance ---
    path("maintenance/create/", MaintenanceCreateView.as_view(), name="create-maintenance"),
    path("maintenance/", MaintenanceExpenseListView.as_view(), name="maintenance-list"),
    path("maintenance/<int:pk>/", MaintenanceExpenseDetailView.as_view(), name="maintenance-detail"),

    # --- Reports ---
    path("report/", ExpenseReportView.as_view(), name="expense-report"),

    # --- Staff Management ---
    path("staff/", StaffListCreateView.as_view(), name="staff-list-create"),
    path("staff/<int:pk>/", StaffDetailView.as_view(), name="staff-detail"),

    # --- Staff Salary ---
    path("staff/salary/add/", AddStaffSalaryView.as_view(), name="add-staff-salary"),
    path("staff/salary/detail/<int:staff_id>/", StaffSalaryDetailView.as_view(), name="staff-salary-detail"),
    path("staff/salary/list/", StaffSalaryListView.as_view(), name="staff-salary-list"),
    path("staff/salary/report/", StaffSalaryReportView.as_view(), name="staff-salary-report"),

    # --- Vendors ---
    path("vendors/", VendorListCreateView.as_view(), name="vendor-list-create"),
    path("vendors/<int:pk>/", VendorDetailView.as_view(), name="vendor-detail"),

    # --- Raw Material Expenses ---
    path("raw-materials/", RawMaterialExpenseListCreateView.as_view(), name="raw-material-list-create"),
    path("raw-materials/<int:pk>/", RawMaterialExpenseDetailView.as_view(), name="raw-material-detail"),
]