from django.db.models import (
    Sum,
    Count
)

from rest_framework.views import (
    APIView
)

from rest_framework.permissions import (
    IsAuthenticated
)

from rest_framework.response import (
    Response
)

from shops.models import Shop

from orders.models import Order

from expenses.models import (
    ExpenseEntry
)

from accounts.models import (
    User,
    CustomerProfile
)

from datetime import datetime

from django.db.models import Sum

from django.utils import timezone

from orders.models import Order

from expenses.models import (
    ExpenseEntry,
    MaintenanceExpense
)

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.http import HttpResponse

from openpyxl import Workbook

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import (
    getSampleStyleSheet
)

from django.db.models import Sum



class ManagerDashboardView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        if (
            request.user.role
            !=
            "manager"
        ):

            return Response(
                {
                    "error":
                    "Permission denied"
                },
                status=403
            )

        shop = (
            request.user
            .managerprofile
            .shop
        )

        orders = Order.objects.filter(
            shop=shop
        )

        expenses = (
            ExpenseEntry.objects
            .filter(
                shop=shop
            )
        )

        total_sales = (
            orders
            .filter(
                status="collected"
            )
            .aggregate(
                total=
                Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        total_expenses = (
            expenses.aggregate(
                total=
                Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        return Response({

            "shop":
            shop.name,

            "total_orders":
            orders.count(),

            "pending_orders":
            orders.filter(
                status="pending"
            ).count(),

            "accepted_orders":
            orders.filter(
                status="accepted"
            ).count(),

            "preparing_orders":
            orders.filter(
                status="preparing"
            ).count(),

            "ready_orders":
            orders.filter(
                status="ready"
            ).count(),

            "completed_orders":
            orders.filter(
                status="collected"
            ).count(),

            "cancelled_orders":
            orders.filter(
                status="cancelled"
            ).count(),

            "sales":
            total_sales,

            "expenses":
            total_expenses,

            "profit":
            total_sales
            -
            total_expenses
        })
        

class SuperAdminDashboardView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        if (
            request.user.role
            !=
            "super_admin"
        ):

            return Response(
                {
                    "error":
                    "Permission denied"
                },
                status=403
            )

        total_sales = (
            Order.objects
            .filter(
                status="collected"
            )
            .aggregate(
                total=
                Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        total_expenses = (
            ExpenseEntry.objects
            .aggregate(
                total=
                Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        return Response({

            "shops":
            Shop.objects.count(),

            "customers":
            User.objects.filter(
                role="customer"
            ).count(),

            "managers":
            User.objects.filter(
                role="manager"
            ).count(),

            "flagged_customers":
            CustomerProfile.objects.filter(
                is_flagged=True
            ).count(),

            "orders":
            Order.objects.count(),

            "sales":
            total_sales,

            "expenses":
            total_expenses,

            "profit":
            total_sales
            -
            total_expenses
        })
        

class ShopSummaryView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request,
        shop_id
    ):

        try:

            shop = Shop.objects.get(
                id=shop_id
            )

        except Shop.DoesNotExist:

            return Response(
                {
                    "error":
                    "Shop not found"
                },
                status=404
            )

        orders = Order.objects.filter(
            shop=shop
        )

        expenses = (
            ExpenseEntry.objects
            .filter(
                shop=shop
            )
        )

        sales = (
            orders.filter(
                status="collected"
            )
            .aggregate(
                total=
                Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        expense_total = (
            expenses.aggregate(
                total=
                Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        return Response({

            "shop":
            shop.name,

            "orders":
            orders.count(),

            "sales":
            sales,

            "expenses":
            expense_total,

            "profit":
            sales
            -
            expense_total
        })
        
class CustomerStatsView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        customers = (
            CustomerProfile.objects
            .all()
        )

        return Response({

            "total_customers":
            customers.count(),

            "flagged":
            customers.filter(
                is_flagged=True
            ).count(),

            "high_trust":
            customers.filter(
                trust_score__gte=90
            ).count(),

            "low_trust":
            customers.filter(
                trust_score__lt=50
            ).count()
        })
        
class DailySalesReportView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        today = timezone.now().date()

        orders = Order.objects.filter(
            status="collected",
            ordered_at__date=today
        )

        total_sales = (
            orders.aggregate(
                total=Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        return Response({

            "date":
            str(today),

            "orders":
            orders.count(),

            "sales":
            total_sales
        })

class MonthlySalesReportView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        now = timezone.now()

        orders = Order.objects.filter(
            status="collected",
            ordered_at__year=now.year,
            ordered_at__month=now.month
        )

        total_sales = (
            orders.aggregate(
                total=Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        return Response({

            "year":
            now.year,

            "month":
            now.month,

            "orders":
            orders.count(),

            "sales":
            total_sales
        })
        
class SalesReportView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        start = request.GET.get(
            "start"
        )

        end = request.GET.get(
            "end"
        )

        orders = Order.objects.filter(
            status="collected",
            ordered_at__date__range=[
                start,
                end
            ]
        )

        total_sales = (
            orders.aggregate(
                total=Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        return Response({

            "start":
            start,

            "end":
            end,

            "orders":
            orders.count(),

            "sales":
            total_sales
        })
        
class ExpenseReportView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        start = request.GET.get(
            "start"
        )

        end = request.GET.get(
            "end"
        )

        expenses = (
            ExpenseEntry.objects
            .filter(
                expense_date__range=[
                    start,
                    end
                ]
            )
        )

        total_expense = (
            expenses.aggregate(
                total=Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        return Response({

            "start":
            start,

            "end":
            end,

            "expenses":
            total_expense,

            "records":
            expenses.count()
        })
        
class MaintenanceExpenseReportView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        start = request.GET.get(
            "start"
        )

        end = request.GET.get(
            "end"
        )

        expenses = (
            MaintenanceExpense.objects
            .filter(
                maintenance_date__range=[
                    start,
                    end
                ]
            )
        )

        total = (
            expenses.aggregate(
                total=Sum(
                    "amount"
                )
            )["total"]
            or 0
        )

        return Response({

            "records":
            expenses.count(),

            "maintenance":
            total
        })
        
        
        
class ProfitLossReportView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        start = request.GET.get(
            "start"
        )

        end = request.GET.get(
            "end"
        )

        sales = (
            Order.objects.filter(
                status="collected",
                ordered_at__date__range=[
                    start,
                    end
                ]
            )
            .aggregate(
                total=Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        expenses = (
            ExpenseEntry.objects.filter(
                expense_date__range=[
                    start,
                    end
                ]
            )
            .aggregate(
                total=Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        maintenance = (
            MaintenanceExpense.objects.filter(
                maintenance_date__range=[
                    start,
                    end
                ]
            )
            .aggregate(
                total=Sum(
                    "amount"
                )
            )["total"]
            or 0
        )

        total_expense = (
            expenses +
            maintenance
        )

        return Response({

            "sales":
            sales,

            "expenses":
            expenses,

            "maintenance":
            maintenance,

            "total_expenses":
            total_expense,

            "profit":
            sales -
            total_expense
        })
        

class ShopSalesReportView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request,
        shop_id
    ):

        orders = Order.objects.filter(
            shop_id=shop_id,
            status="collected"
        )

        sales = (
            orders.aggregate(
                total=Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        return Response({

            "shop_id":
            shop_id,

            "orders":
            orders.count(),

            "sales":
            sales
        })
        

class ShopExpenseReportView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request,
        shop_id
    ):

        expenses = (
            ExpenseEntry.objects
            .filter(
                shop_id=shop_id
            )
        )

        total = (
            expenses.aggregate(
                total=Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        return Response({

            "shop_id":
            shop_id,

            "records":
            expenses.count(),

            "expense":
            total
        })
        

class ExportSalesExcelView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        wb = Workbook()

        ws = wb.active

        ws.title = "Sales Report"

        ws.append([
            "Order Number",
            "Customer",
            "Shop",
            "Amount",
            "Status",
            "Date"
        ])

        orders = Order.objects.all()

        for order in orders:

            ws.append([

                order.order_number,

                (
                    order.customer.username
                    if order.customer
                    else "-"
                ),

                order.shop.name,

                float(
                    order.total_amount
                ),

                order.status,

                str(
                    order.ordered_at
                )
            ])

        response = HttpResponse(
            content_type=
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        response[
            "Content-Disposition"
        ] = (
            'attachment; filename="sales_report.xlsx"'
        )

        wb.save(response)

        return response
    

class ExportExpenseExcelView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        wb = Workbook()

        ws = wb.active

        ws.title = "Expense Report"

        ws.append([
            "Shop",
            "Category",
            "Amount",
            "Date"
        ])

        expenses = (
            ExpenseEntry.objects
            .all()
        )

        for expense in expenses:

            ws.append([

                expense.shop.name,

                expense.category.name,

                float(
                    expense.total_amount
                ),

                str(
                    expense.expense_date
                )
            ])

        response = HttpResponse(
            content_type=
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        response[
            "Content-Disposition"
        ] = (
            'attachment; filename="expense_report.xlsx"'
        )

        wb.save(response)

        return response
    

class ExportSalesPDFView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        response = HttpResponse(
            content_type=
            "application/pdf"
        )

        response[
            "Content-Disposition"
        ] = (
            'attachment; filename="sales_report.pdf"'
        )

        doc = SimpleDocTemplate(
            response
        )

        styles = (
            getSampleStyleSheet()
        )

        elements = []

        elements.append(
            Paragraph(
                "Sales Report",
                styles["Title"]
            )
        )

        elements.append(
            Spacer(1, 20)
        )

        orders = Order.objects.all()

        for order in orders:

            elements.append(
                Paragraph(
                    f"{order.order_number} - ₹{order.total_amount}",
                    styles["Normal"]
                )
            )

        doc.build(
            elements
        )

        return response
    
class ExportExpensePDFView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        response = HttpResponse(
            content_type=
            "application/pdf"
        )

        response[
            "Content-Disposition"
        ] = (
            'attachment; filename="expense_report.pdf"'
        )

        doc = SimpleDocTemplate(
            response
        )

        styles = (
            getSampleStyleSheet()
        )

        elements = []

        elements.append(
            Paragraph(
                "Expense Report",
                styles["Title"]
            )
        )

        elements.append(
            Spacer(1, 20)
        )

        expenses = (
            ExpenseEntry.objects
            .all()
        )

        for expense in expenses:

            elements.append(
                Paragraph(
                    f"{expense.shop.name} - ₹{expense.total_amount}",
                    styles["Normal"]
                )
            )

        doc.build(
            elements
        )

        return response
    

class TopShopsView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        shops = []

        for shop in Shop.objects.all():

            sales = (
                Order.objects
                .filter(
                    shop=shop,
                    status="collected"
                )
                .aggregate(
                    total=Sum(
                        "total_amount"
                    )
                )["total"]
                or 0
            )

            shops.append({

                "shop":
                shop.name,

                "sales":
                sales
            })

        shops = sorted(
            shops,
            key=lambda x:
            x["sales"],
            reverse=True
        )

        return Response(
            shops
        )
        

class TopCustomersView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        customers = []

        for customer in User.objects.filter(
            role="customer"
        ):

            sales = (
                Order.objects
                .filter(
                    customer=customer,
                    status="collected"
                )
                .aggregate(
                    total=Sum(
                        "total_amount"
                    )
                )["total"]
                or 0
            )

            customers.append({

                "customer":
                customer.username,

                "phone":
                customer.phone,

                "sales":
                sales
            })

        customers = sorted(
            customers,
            key=lambda x:
            x["sales"],
            reverse=True
        )

        return Response(
            customers
        )
        
class KPIDashboardView(
    APIView
):

    permission_classes = [
        IsAuthenticated
    ]

    def get(
        self,
        request
    ):

        sales = (
            Order.objects
            .filter(
                status="collected"
            )
            .aggregate(
                total=Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        expenses = (
            ExpenseEntry.objects
            .aggregate(
                total=Sum(
                    "total_amount"
                )
            )["total"]
            or 0
        )

        total_orders = (
            Order.objects.count()
        )

        completed_orders = (
            Order.objects.filter(
                status="collected"
            ).count()
        )

        return Response({

            "sales":
            sales,

            "expenses":
            expenses,

            "profit":
            sales - expenses,

            "orders":
            total_orders,

            "completed":
            completed_orders,

            "completion_rate":
            round(
                (
                    completed_orders
                    /
                    total_orders
                    * 100
                )
                if total_orders
                else 0,
                2
            )
        })
        

