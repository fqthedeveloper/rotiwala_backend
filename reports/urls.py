from django.urls import path

from .views import (
    ManagerDashboardView,
    SuperAdminDashboardView,
    ShopSummaryView,
    CustomerStatsView,
    DailySalesReportView,
    MonthlySalesReportView,
    SalesReportView,
    ExpenseReportView,
    MaintenanceExpenseReportView,
    ProfitLossReportView,
    ShopSalesReportView,
    ShopExpenseReportView,
    ExportSalesExcelView,
    ExportExpenseExcelView,
    ExportSalesPDFView,
    ExportExpensePDFView,
    TopShopsView,
    TopCustomersView,
    KPIDashboardView
)

urlpatterns = [

    path(
        "dashboard/manager/",
        ManagerDashboardView.as_view()
    ),

    path(
        "dashboard/admin/",
        SuperAdminDashboardView.as_view()
    ),

    path(
        "shop/<int:shop_id>/",
        ShopSummaryView.as_view()
    ),

    path(
        "customers/",
        CustomerStatsView.as_view()
    ),
    path(
        "sales/daily/",
        DailySalesReportView.as_view()
    ),

    path(
        "sales/monthly/",
        MonthlySalesReportView.as_view()
    ),

    path(
        "sales/",
        SalesReportView.as_view()
    ),

    path(
        "expenses/",
        ExpenseReportView.as_view()
    ),

    path(
        "maintenance/",
        MaintenanceExpenseReportView.as_view()
    ),

    path(
        "profit-loss/",
        ProfitLossReportView.as_view()
    ),

    path(
        "shop/<int:shop_id>/sales/",
        ShopSalesReportView.as_view()
    ),

    path(
        "shop/<int:shop_id>/expenses/",
        ShopExpenseReportView.as_view()
    ),
    
    path(
        "export/sales/excel/",
        ExportSalesExcelView.as_view()
    ),

    path(
        "export/expenses/excel/",
        ExportExpenseExcelView.as_view()
    ),

    path(
        "export/sales/pdf/",
        ExportSalesPDFView.as_view()
    ),

    path(
        "export/expenses/pdf/",
        ExportExpensePDFView.as_view()
    ),

    path(
        "top-shops/",
        TopShopsView.as_view()
    ),

    path(
        "top-customers/",
        TopCustomersView.as_view()
    ),

    path(
        "kpi/",
        KPIDashboardView.as_view()
    ),
]