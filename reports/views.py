# reports/views.py
import io
from datetime import datetime, timedelta
from calendar import monthrange

from django.db.models import Sum, Q
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response

from openpyxl import Workbook
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch

from shops.models import Shop
from orders.models import Order
from expenses.models import ExpenseEntry, MaintenanceExpense, StaffSalaryRecord
from accounts.models import User, CustomerProfile
from accounts.models import ManagerProfile


# ---------------------------------------------------------------------
# Custom renderer to bypass DRF content negotiation for file downloads
# ---------------------------------------------------------------------
class AnyRenderer(BaseRenderer):
    media_type = '*/*'
    format = 'bin'

    def render(self, data, media_type=None, renderer_context=None):
        # data is already the HttpResponse content; just return it
        return data


# ---------------------------------------------------------------------
# Helper: resolve manager shop
# ---------------------------------------------------------------------
def _get_manager_shop(user, query_shop_id=None):
    """Resolve manager's shop with multiple fallbacks."""
    shop = None
    if hasattr(user, 'manager_profile') and user.manager_profile:
        shop = user.manager_profile.shop
    if not shop and hasattr(user, 'shop') and user.shop:
        shop = user.shop
    if not shop and hasattr(user, 'shop_id') and user.shop_id:
        try:
            shop = Shop.objects.get(id=user.shop_id)
        except Shop.DoesNotExist:
            pass
    if not shop and query_shop_id:
        try:
            shop = Shop.objects.get(id=query_shop_id)
        except Shop.DoesNotExist:
            pass
    return shop


# ---------------------------------------------------------------------
# Legacy dashboard views (unchanged but with corrected field names)
# ---------------------------------------------------------------------

class ManagerDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if request.user.role != "manager":
            return Response({"error": "Permission denied"}, status=403)
        shop = request.user.manager_profile.shop
        orders = Order.objects.filter(shop=shop)
        expenses = ExpenseEntry.objects.filter(shop=shop)
        total_sales = orders.filter(status="collected").aggregate(total=Sum("total_amount"))["total"] or 0
        total_expenses = expenses.aggregate(total=Sum("total_amount"))["total"] or 0
        return Response({
            "shop": shop.name,
            "total_orders": orders.count(),
            "pending_orders": orders.filter(status="pending").count(),
            "accepted_orders": orders.filter(status="accepted").count(),
            "preparing_orders": orders.filter(status="preparing").count(),
            "ready_orders": orders.filter(status="ready").count(),
            "completed_orders": orders.filter(status="collected").count(),
            "cancelled_orders": orders.filter(status="cancelled").count(),
            "sales": total_sales,
            "expenses": total_expenses,
            "profit": total_sales - total_expenses,
        })


class SuperAdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        if request.user.role != "super_admin":
            return Response({"error": "Permission denied"}, status=403)
        total_sales = Order.objects.filter(status="collected").aggregate(total=Sum("total_amount"))["total"] or 0
        total_expenses = ExpenseEntry.objects.aggregate(total=Sum("total_amount"))["total"] or 0
        return Response({
            "shops": Shop.objects.count(),
            "customers": User.objects.filter(role="customer").count(),
            "managers": User.objects.filter(role="manager").count(),
            "flagged_customers": CustomerProfile.objects.filter(is_flagged=True).count(),
            "orders": Order.objects.count(),
            "sales": total_sales,
            "expenses": total_expenses,
            "profit": total_sales - total_expenses,
        })


class ShopSummaryView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, shop_id):
        try:
            shop = Shop.objects.get(id=shop_id)
        except Shop.DoesNotExist:
            return Response({"error": "Shop not found"}, status=404)
        orders = Order.objects.filter(shop=shop)
        expenses = ExpenseEntry.objects.filter(shop=shop)
        sales = orders.filter(status="collected").aggregate(total=Sum("total_amount"))["total"] or 0
        expense_total = expenses.aggregate(total=Sum("total_amount"))["total"] or 0
        return Response({
            "shop": shop.name,
            "orders": orders.count(),
            "sales": sales,
            "expenses": expense_total,
            "profit": sales - expense_total,
        })


class CustomerStatsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        customers = CustomerProfile.objects.all()
        return Response({
            "total_customers": customers.count(),
            "flagged": customers.filter(is_flagged=True).count(),
            "high_trust": customers.filter(trust_score__gte=90).count(),
            "low_trust": customers.filter(trust_score__lt=50).count(),
        })


class DailySalesReportView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        today = timezone.now().date()
        orders = Order.objects.filter(status="collected", ordered_at__date=today)
        total_sales = orders.aggregate(total=Sum("total_amount"))["total"] or 0
        return Response({"date": str(today), "orders": orders.count(), "sales": total_sales})


class MonthlySalesReportView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        now = timezone.now()
        orders = Order.objects.filter(status="collected", ordered_at__year=now.year, ordered_at__month=now.month)
        total_sales = orders.aggregate(total=Sum("total_amount"))["total"] or 0
        return Response({"year": now.year, "month": now.month, "orders": orders.count(), "sales": total_sales})


class SalesReportView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        start = request.GET.get("start")
        end = request.GET.get("end")
        orders = Order.objects.filter(status="collected", ordered_at__date__range=[start, end])
        total_sales = orders.aggregate(total=Sum("total_amount"))["total"] or 0
        return Response({"start": start, "end": end, "orders": orders.count(), "sales": total_sales})


# Fixed: ExpenseReportView uses entry_datetime
class ExpenseReportView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        start = request.GET.get("start")
        end = request.GET.get("end")
        expenses = ExpenseEntry.objects.filter(entry_datetime__date__range=[start, end])
        total_expense = expenses.aggregate(total=Sum("total_amount"))["total"] or 0
        return Response({"start": start, "end": end, "expenses": total_expense, "records": expenses.count()})


class MaintenanceExpenseReportView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        start = request.GET.get("start")
        end = request.GET.get("end")
        expenses = MaintenanceExpense.objects.filter(maintenance_date__range=[start, end])
        total = expenses.aggregate(total=Sum("amount"))["total"] or 0
        return Response({"records": expenses.count(), "maintenance": total})


class ProfitLossReportView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        start = request.GET.get("start")
        end = request.GET.get("end")
        sales = Order.objects.filter(status="collected", ordered_at__date__range=[start, end]).aggregate(total=Sum("total_amount"))["total"] or 0
        expenses = ExpenseEntry.objects.filter(entry_datetime__date__range=[start, end]).aggregate(total=Sum("total_amount"))["total"] or 0
        maintenance = MaintenanceExpense.objects.filter(maintenance_date__range=[start, end]).aggregate(total=Sum("amount"))["total"] or 0
        total_expense = expenses + maintenance
        return Response({
            "sales": sales,
            "expenses": expenses,
            "maintenance": maintenance,
            "total_expenses": total_expense,
            "profit": sales - total_expense,
        })


class ShopSalesReportView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, shop_id):
        orders = Order.objects.filter(shop_id=shop_id, status="collected")
        sales = orders.aggregate(total=Sum("total_amount"))["total"] or 0
        return Response({"shop_id": shop_id, "orders": orders.count(), "sales": sales})


class ShopExpenseReportView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, shop_id):
        expenses = ExpenseEntry.objects.filter(shop_id=shop_id)
        total = expenses.aggregate(total=Sum("total_amount"))["total"] or 0
        return Response({"shop_id": shop_id, "records": expenses.count(), "expense": total})


# ---------------------------------------------------------------------
# Export Views (Fixed: use entry_datetime, include staff salary)
# ---------------------------------------------------------------------

class ExportSalesExcelView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        wb = Workbook()
        ws = wb.active
        ws.title = "Sales Report"
        ws.append(["Order Number", "Customer", "Shop", "Amount", "Status", "Date"])
        for order in Order.objects.all():
            ws.append([
                order.order_number,
                order.customer.username if order.customer else "-",
                order.shop.name,
                float(order.total_amount),
                order.status,
                str(order.ordered_at),
            ])
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="sales_report.xlsx"'
        wb.save(response)
        return response


class ExportExpenseExcelView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        wb = Workbook()
        ws = wb.active
        ws.title = "Expense Report"
        ws.append(["Shop", "Category", "Amount", "Date"])
        for expense in ExpenseEntry.objects.all():
            ws.append([
                expense.shop.name,
                expense.category.name,
                float(expense.total_amount),
                str(expense.entry_datetime.date()),
            ])
        response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response["Content-Disposition"] = 'attachment; filename="expense_report.xlsx"'
        wb.save(response)
        return response


class ExportSalesPDFView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="sales_report.pdf"'
        doc = SimpleDocTemplate(response)
        styles = getSampleStyleSheet()
        elements = [Paragraph("Sales Report", styles["Title"]), Spacer(1, 20)]
        for order in Order.objects.all():
            elements.append(Paragraph(f"{order.order_number} - ₹{order.total_amount}", styles["Normal"]))
        doc.build(elements)
        return response


class ExportExpensePDFView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        response = HttpResponse(content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="expense_report.pdf"'
        doc = SimpleDocTemplate(response)
        styles = getSampleStyleSheet()
        elements = [Paragraph("Expense Report", styles["Title"]), Spacer(1, 20)]
        for expense in ExpenseEntry.objects.all():
            elements.append(Paragraph(f"{expense.shop.name} - ₹{expense.total_amount}", styles["Normal"]))
        doc.build(elements)
        return response


class TopShopsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        shops = []
        for shop in Shop.objects.all():
            sales = Order.objects.filter(shop=shop, status="collected").aggregate(total=Sum("total_amount"))["total"] or 0
            shops.append({"shop": shop.name, "sales": sales})
        shops.sort(key=lambda x: x["sales"], reverse=True)
        return Response(shops)


class TopCustomersView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        customers = []
        for customer in User.objects.filter(role="customer"):
            sales = Order.objects.filter(customer=customer, status="collected").aggregate(total=Sum("total_amount"))["total"] or 0
            customers.append({"customer": customer.username, "phone": customer.phone, "sales": sales})
        customers.sort(key=lambda x: x["sales"], reverse=True)
        return Response(customers)


class KPIDashboardView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        sales = Order.objects.filter(status="collected").aggregate(total=Sum("total_amount"))["total"] or 0
        expenses = ExpenseEntry.objects.aggregate(total=Sum("total_amount"))["total"] or 0
        total_orders = Order.objects.count()
        completed_orders = Order.objects.filter(status="collected").count()
        return Response({
            "sales": sales,
            "expenses": expenses,
            "profit": sales - expenses,
            "orders": total_orders,
            "completed": completed_orders,
            "completion_rate": round((completed_orders / total_orders * 100) if total_orders else 0, 2),
        })


# ---------------------------------------------------------------------
# NEW UNIFIED REPORT AND EXPORT VIEWS (FIXED with renderer)
# ---------------------------------------------------------------------

class ReportView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=401)

        user = request.user
        filter_type = request.query_params.get('filter', 'today')
        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')
        shop_id = request.query_params.get('shop')

        # Date range
        today = timezone.now().date()
        if filter_type == 'today':
            start_date = end_date = today
        elif filter_type == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
        elif filter_type == 'month':
            start_date = today.replace(day=1)
            end_date = today.replace(day=monthrange(today.year, today.month)[1])
        elif filter_type == 'custom' and start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            start_date = end_date = today

        # Shop filter
        shop_filter = Q()
        if user.role == 'manager':
            shop = _get_manager_shop(user, shop_id)
            if not shop:
                return Response({"error": "Manager has no shop."}, status=400)
            shop_filter = Q(shop=shop)
        else:
            if shop_id:
                shop_filter = Q(shop_id=shop_id)

        # Data
        sales_qs = Order.objects.filter(
            status='collected',
            ordered_at__date__gte=start_date,
            ordered_at__date__lte=end_date
        ).filter(shop_filter)
        total_sales = sales_qs.aggregate(total=Sum('total_amount'))['total'] or 0
        order_count = sales_qs.count()

        expense_qs = ExpenseEntry.objects.filter(
            entry_datetime__date__gte=start_date,
            entry_datetime__date__lte=end_date
        ).filter(shop_filter)
        total_expenses = expense_qs.aggregate(total=Sum('total_amount'))['total'] or 0

        maint_qs = MaintenanceExpense.objects.filter(
            maintenance_date__gte=start_date,
            maintenance_date__lte=end_date
        ).filter(shop_filter)
        total_maintenance = maint_qs.aggregate(total=Sum('amount'))['total'] or 0

        staff_salary_qs = StaffSalaryRecord.objects.filter(
            payment_date__gte=start_date,
            payment_date__lte=end_date
        ).filter(shop_filter)
        total_staff_salary = staff_salary_qs.aggregate(total=Sum('amount'))['total'] or 0

        total_outgoing = total_expenses + total_maintenance + total_staff_salary
        profit = total_sales - total_outgoing

        # Shop breakdown (for super_admin)
        shops_data = None
        if user.role == 'super_admin':
            shops = Shop.objects.all()
            if shop_id:
                shops = shops.filter(id=shop_id)
            shops_data = []
            for s in shops:
                s_sales = Order.objects.filter(
                    status='collected',
                    ordered_at__date__gte=start_date,
                    ordered_at__date__lte=end_date,
                    shop=s
                ).aggregate(total=Sum('total_amount'))['total'] or 0
                s_exp = ExpenseEntry.objects.filter(
                    entry_datetime__date__gte=start_date,
                    entry_datetime__date__lte=end_date,
                    shop=s
                ).aggregate(total=Sum('total_amount'))['total'] or 0
                s_maint = MaintenanceExpense.objects.filter(
                    maintenance_date__gte=start_date,
                    maintenance_date__lte=end_date,
                    shop=s
                ).aggregate(total=Sum('amount'))['total'] or 0
                s_salary = StaffSalaryRecord.objects.filter(
                    payment_date__gte=start_date,
                    payment_date__lte=end_date,
                    shop=s
                ).aggregate(total=Sum('amount'))['total'] or 0
                shops_data.append({
                    'shop_id': s.id,
                    'shop_name': s.name,
                    'sales': s_sales,
                    'expenses': s_exp,
                    'maintenance': s_maint,
                    'staff_salary': s_salary,
                    'profit': s_sales - (s_exp + s_maint + s_salary)
                })

        return Response({
            'filter': {
                'type': filter_type,
                'start': start_date.isoformat(),
                'end': end_date.isoformat(),
            },
            'summary': {
                'sales': total_sales,
                'orders': order_count,
                'expenses': total_expenses,
                'maintenance': total_maintenance,
                'staff_salary': total_staff_salary,
                'total_outgoing': total_outgoing,
                'profit': profit,
            },
            'shops': shops_data,
        })


class ExportReportView(APIView):
    permission_classes = [IsAuthenticated]
    renderer_classes = (AnyRenderer,)  # <-- FIX: Bypass content negotiation

    def get(self, request):
        # Parse parameters
        format_type = (request.query_params.get('format') or request.query_params.get('file') or 'excel').lower()
        filter_type = request.query_params.get('filter', 'today')
        start_date = request.query_params.get('start')
        end_date = request.query_params.get('end')
        shop_id = request.query_params.get('shop')

        # Date range
        today = timezone.now().date()
        if filter_type == 'today':
            start_date = end_date = today
        elif filter_type == 'week':
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
        elif filter_type == 'month':
            start_date = today.replace(day=1)
            end_date = today.replace(day=monthrange(today.year, today.month)[1])
        elif filter_type == 'custom' and start_date and end_date:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            start_date = end_date = today

        # Shop filter
        user = request.user
        shop_filter = Q()
        if user.role == 'manager':
            shop = _get_manager_shop(user, shop_id)
            if not shop:
                return HttpResponse(
                    '{"error": "Manager has no shop."}',
                    status=400,
                    content_type='application/json'
                )
            shop_filter = Q(shop=shop)
        else:
            if shop_id:
                shop_filter = Q(shop_id=shop_id)

        # Data
        sales_qs = Order.objects.filter(
            status='collected',
            ordered_at__date__gte=start_date,
            ordered_at__date__lte=end_date
        ).filter(shop_filter)
        total_sales = sales_qs.aggregate(total=Sum('total_amount'))['total'] or 0
        order_count = sales_qs.count()

        expense_qs = ExpenseEntry.objects.filter(
            entry_datetime__date__gte=start_date,
            entry_datetime__date__lte=end_date
        ).filter(shop_filter)
        total_expenses = expense_qs.aggregate(total=Sum('total_amount'))['total'] or 0

        maint_qs = MaintenanceExpense.objects.filter(
            maintenance_date__gte=start_date,
            maintenance_date__lte=end_date
        ).filter(shop_filter)
        total_maintenance = maint_qs.aggregate(total=Sum('amount'))['total'] or 0

        staff_salary_qs = StaffSalaryRecord.objects.filter(
            payment_date__gte=start_date,
            payment_date__lte=end_date
        ).filter(shop_filter)
        total_staff_salary = staff_salary_qs.aggregate(total=Sum('amount'))['total'] or 0

        total_outgoing = total_expenses + total_maintenance + total_staff_salary
        profit = total_sales - total_outgoing

        # Generate file
        if format_type == 'excel':
            return self._generate_excel(
                start_date, end_date, sales_qs, expense_qs, maint_qs, staff_salary_qs,
                total_sales, order_count, total_expenses, total_maintenance, total_staff_salary, profit
            )
        elif format_type == 'pdf':
            return self._generate_pdf(
                start_date, end_date, sales_qs, expense_qs, maint_qs, staff_salary_qs,
                total_sales, order_count, total_expenses, total_maintenance, total_staff_salary, profit
            )
        else:
            return HttpResponse(
                '{"error": "Unsupported format. Use \'excel\' or \'pdf\'."}',
                status=400,
                content_type='application/json'
            )

    # ------------------------------------------------------------------
    # Excel Generator (Deep Information)
    # ------------------------------------------------------------------
    def _generate_excel(self, start_date, end_date, sales_qs, expense_qs, maint_qs, staff_salary_qs,
                        total_sales, order_count, total_expenses, total_maintenance, total_staff_salary, profit):
        wb = Workbook()

        # Sheet 1: Summary
        ws_summary = wb.active
        ws_summary.title = "Summary"
        ws_summary.append(["Report Period", f"{start_date} to {end_date}"])
        ws_summary.append([])
        ws_summary.append(["Metric", "Value (₹)"])
        ws_summary.append(["Total Sales", total_sales])
        ws_summary.append(["Orders", order_count])
        ws_summary.append(["Expenses", total_expenses])
        ws_summary.append(["Maintenance", total_maintenance])
        ws_summary.append(["Staff Salary", total_staff_salary])
        ws_summary.append(["Total Outgoing", total_expenses + total_maintenance + total_staff_salary])
        ws_summary.append(["Profit", profit])

        # Sheet 2: Orders
        ws_orders = wb.create_sheet("Orders")
        ws_orders.append(["Order #", "Customer", "Shop", "Amount (₹)", "Status", "Date"])
        for order in sales_qs.select_related('customer', 'shop'):
            ws_orders.append([
                order.order_number,
                order.customer.username if order.customer else "-",
                order.shop.name,
                float(order.total_amount),
                order.status,
                order.ordered_at.strftime("%Y-%m-%d %H:%M")
            ])

        # Sheet 3: Expenses (Header)
        ws_expenses = wb.create_sheet("Expenses")
        ws_expenses.append([
            "Expense ID", "Shop", "Category", "Created By", "Expense Date", "Total Amount (₹)", "Notes"
        ])
        for exp in expense_qs.select_related('shop', 'category', 'created_by'):
            created_by = exp.created_by.username if exp.created_by else "-"
            ws_expenses.append([
                exp.id,
                exp.shop.name,
                exp.category.name,
                created_by,
                exp.entry_datetime.strftime("%Y-%m-%d"),
                float(exp.total_amount),
                exp.notes or ""
            ])

        # Sheet 4: Expense Items (detailed breakdown)
        ws_exp_items = wb.create_sheet("Expense Items")
        ws_exp_items.append([
            "Expense ID", "Item Name", "Quantity", "Amount (₹)", "Note", "Created At"
        ])
        for exp in expense_qs.prefetch_related('expense_items').only('id'):
            for item in exp.expense_items.all():
                ws_exp_items.append([
                    exp.id,
                    item.item_name,
                    float(item.quantity) if item.quantity is not None else "",
                    float(item.amount),
                    item.note or "",
                    item.created_at.strftime("%Y-%m-%d %H:%M:%S") if item.created_at else "",
                ])

        # Sheet 5: Maintenance
        ws_maint = wb.create_sheet("Maintenance")
        ws_maint.append(["ID", "Shop", "Title", "Description", "Amount (₹)", "Date", "Created By"])
        for m in maint_qs.select_related('shop', 'created_by'):
            created_by = m.created_by.username if m.created_by else "-"
            ws_maint.append([
                m.id,
                m.shop.name,
                m.title,
                m.description or "",
                float(m.amount),
                m.maintenance_date.strftime("%Y-%m-%d"),
                created_by
            ])

        # Sheet 6: Staff Salary Records
        ws_salary = wb.create_sheet("Staff Salary")
        ws_salary.append([
            "Record ID", "Staff Name", "Shop", "Amount (₹)", "Payment Date",
            "Payment Method", "UTR Number", "Payment Type", "Notes", "Created By"
        ])
        for rec in staff_salary_qs.select_related('staff', 'shop', 'created_by'):
            created_by = rec.created_by.username if rec.created_by else "-"
            ws_salary.append([
                rec.id,
                rec.staff.name,
                rec.shop.name,
                float(rec.amount),
                rec.payment_date.strftime("%Y-%m-%d"),
                rec.get_payment_method_display(),
                rec.utr_number or "",
                rec.get_payment_type_display(),
                rec.notes or "",
                created_by
            ])

        # Build response
        response = HttpResponse(
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="report_{start_date}_to_{end_date}.xlsx"'
        wb.save(response)
        return response

    # ------------------------------------------------------------------
    # PDF Generator (Brief)
    # ------------------------------------------------------------------
    def _generate_pdf(self, start_date, end_date, sales_qs, expense_qs, maint_qs, staff_salary_qs,
                      total_sales, order_count, total_expenses, total_maintenance, total_staff_salary, profit):
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="report_{start_date}_to_{end_date}.pdf"'

        doc = SimpleDocTemplate(response, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        title_style = styles['Title']
        elements.append(Paragraph(f"Financial Report: {start_date} to {end_date}", title_style))
        elements.append(Spacer(1, 0.2 * inch))

        # Summary table
        summary_data = [
            ['Metric', 'Value (₹)'],
            ['Total Sales', f"{total_sales:,.2f}"],
            ['Orders', str(order_count)],
            ['Expenses', f"{total_expenses:,.2f}"],
            ['Maintenance', f"{total_maintenance:,.2f}"],
            ['Staff Salary', f"{total_staff_salary:,.2f}"],
            ['Total Outgoing', f"{total_expenses + total_maintenance + total_staff_salary:,.2f}"],
            ['Profit', f"{profit:,.2f}"],
        ]
        table = Table(summary_data, colWidths=[2.5 * inch, 2.5 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.3 * inch))

        # Order details (limit to 50)
        elements.append(Paragraph("Order Details (up to 50)", styles['Heading2']))
        order_data = [['Order #', 'Customer', 'Shop', 'Amount (₹)', 'Date']]
        for order in sales_qs.select_related('customer', 'shop')[:50]:
            order_data.append([
                order.order_number,
                order.customer.username if order.customer else '-',
                order.shop.name,
                f"{order.total_amount:,.2f}",
                order.ordered_at.strftime("%Y-%m-%d")
            ])
        if len(order_data) > 1:
            table2 = Table(order_data, colWidths=[1.2*inch, 1.2*inch, 1.2*inch, 1.0*inch, 1.2*inch])
            table2.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table2)
        else:
            elements.append(Paragraph("No orders found.", styles['Normal']))

        # Expenses summary (brief)
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph("Expenses Summary", styles['Heading2']))
        exp_summary = [['Category', 'Total (₹)']]
        exp_by_cat = expense_qs.values('category__name').annotate(total=Sum('total_amount')).order_by('-total')
        for item in exp_by_cat[:20]:
            exp_summary.append([item['category__name'], f"{item['total']:,.2f}"])
        if len(exp_summary) > 1:
            table3 = Table(exp_summary, colWidths=[2.5*inch, 2.5*inch])
            table3.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table3)
        else:
            elements.append(Paragraph("No expenses found.", styles['Normal']))

        # Staff salary summary
        elements.append(Spacer(1, 0.2 * inch))
        elements.append(Paragraph("Staff Salary Summary", styles['Heading2']))
        salary_summary = [['Staff Name', 'Total Paid (₹)']]
        salary_by_staff = staff_salary_qs.values('staff__name').annotate(total=Sum('amount')).order_by('-total')
        for item in salary_by_staff[:20]:
            salary_summary.append([item['staff__name'], f"{item['total']:,.2f}"])
        if len(salary_summary) > 1:
            table4 = Table(salary_summary, colWidths=[2.5*inch, 2.5*inch])
            table4.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ]))
            elements.append(table4)
        else:
            elements.append(Paragraph("No salary records found.", styles['Normal']))

        doc.build(elements)
        return response


class TestView(APIView):
    def get(self, request):
        return Response({"message": "Test view works!"})


# reports/views.py
from django.db.models import Count
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from shops.models import Shop
from orders.models import Order
from menu.models import MenuItem
from accounts.models import User


class PublicStatsView(APIView):
    """Public endpoint for homepage stats (no auth required)"""
    permission_classes = [AllowAny]

    def get(self, request):
        total_shops = Shop.objects.filter(is_active=True).count()
        total_customers = User.objects.filter(role='customer').count()
        total_menu_items = MenuItem.objects.filter(is_active=True).count()
        # Daily orders: orders placed today
        today = timezone.now().date()
        daily_orders = Order.objects.filter(ordered_at__date=today).count()

        return Response({
            'shops': total_shops,
            'daily_orders': daily_orders,
            'menu_items': total_menu_items,
            'customers': total_customers,
        })
