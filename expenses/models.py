from django.db import models
from django.utils import timezone
from shops.models import Shop
from accounts.models import User


class ExpenseCategory(models.Model):
    """
    Categories: Raw Material, Staff Salary, etc.
    """
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ExpenseMasterItem(models.Model):
    """
    Master items added ONLY by Super Admin.
    (e.g., Atta, Sugar, Oil for Raw Material category)
    """
    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.CASCADE,
        related_name="items"
    )
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [['category', 'name']]  # Prevent duplicate items in same category

    def __str__(self):
        return self.name


class ExpenseEntry(models.Model):
    """
    Master header for an expense entry (can contain multiple items).
    Now supports Date & Time via entry_datetime.
    """
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    category = models.ForeignKey(ExpenseCategory, on_delete=models.CASCADE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    # Changed from DateField to DateTimeField to capture exact time (10am vs 3pm)
    entry_datetime = models.DateTimeField(default=timezone.now)

    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-entry_datetime']

    def __str__(self):
        return f"{self.shop.name} - {self.category.name} - {self.entry_datetime.strftime('%Y-%m-%d %H:%M')}"


class ExpenseItemEntry(models.Model):
    """
    Individual line items inside an ExpenseEntry.
    For Raw: uses master_item + quantity + amount.
    For Salary: uses custom_item_name (Staff Name) + amount + note.
    """
    expense = models.ForeignKey(
        ExpenseEntry,
        on_delete=models.CASCADE,
        related_name="expense_items"
    )
    master_item = models.ForeignKey(
        ExpenseMasterItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    custom_item_name = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def item_name(self):
        if self.master_item:
            return self.master_item.name
        return self.custom_item_name

    def __str__(self):
        return self.item_name


class MaintenanceExpense(models.Model):
    """
    Separate model for Maintenance. Managers can add these.
    """
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    maintenance_date = models.DateField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-maintenance_date']

    def __str__(self):
        return self.title



class Staff(models.Model):
    """Staff members (e.g., chefs, waiters)"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='staff')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15, blank=True, null=True)
    monthly_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.shop.name})"


class StaffSalaryRecord(models.Model):
    """
    Individual salary/advance records for staff.
    """
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('ONLINE', 'Online'),
    ]

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='salary_records')
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE)
    expense_entry = models.ForeignKey(
        ExpenseEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='salary_records'
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS, default='CASH')
    utr_number = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    PAYMENT_TYPES = [
        ('MONTHLY', 'Monthly Salary'),
        ('ADVANCE', 'Advance Payment'),
        ('BONUS', 'Bonus'),
        ('DEDUCTION', 'Deduction'),
        ('EMERGENCY', 'Emergency Advance'),
    ]
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default='MONTHLY')

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"{self.staff.name} - {self.payment_date} - ₹{self.amount}"



# ============================================================
# Vendor & Raw Material Expense Models
# ============================================================

class Vendor(models.Model):
    """Vendor/Supplier for raw materials"""
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='vendors')
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = [['shop', 'name']]

    def __str__(self):
        return f"{self.name} ({self.shop.name})"


class RawMaterialExpense(models.Model):
    """
    Detailed raw material expense with vendor, unit, etc.
    """
    UNIT_CHOICES = [
        ('KG', 'Kilogram (kg)'),
        ('ML', 'Milliliter (ml)'),
        ('PIECE', 'Piece'),
        ('OTHER', 'Other'),
    ]

    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='raw_material_expenses')
    vendor = models.ForeignKey(Vendor, on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses')
    item = models.ForeignKey(ExpenseMasterItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='raw_expenses')
    custom_item_name = models.CharField(max_length=200, blank=True, null=True)

    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, default='KG')
    unit_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.TextField(blank=True, null=True)

    expense_date = models.DateField(default=timezone.now)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Optional link to existing ExpenseEntry (for reports)
    expense_entry = models.ForeignKey(
        ExpenseEntry,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='raw_material_items'
    )

    class Meta:
        ordering = ['-expense_date', '-created_at']

    def __str__(self):
        item_name = self.item.name if self.item else self.custom_item_name or "Unknown"
        return f"{item_name} - {self.quantity}{self.get_unit_display()} - ₹{self.amount}"

