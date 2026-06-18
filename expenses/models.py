from django.db import models

from shops.models import Shop
from accounts.models import User


class ExpenseCategory(models.Model):

    name = models.CharField(
        max_length=100,
        unique=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name


class ExpenseMasterItem(models.Model):

    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.CASCADE,
        related_name="items"
    )

    name = models.CharField(
        max_length=200
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name


class ExpenseEntry(models.Model):

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE
    )

    category = models.ForeignKey(
        ExpenseCategory,
        on_delete=models.CASCADE
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    expense_date = models.DateField()

    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    notes = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.shop.name} - {self.category.name}"
    

class ExpenseItemEntry(models.Model):

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

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    note = models.TextField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    @property
    def item_name(self):

        if self.master_item:
            return self.master_item.name

        return self.custom_item_name

    def __str__(self):
        return self.item_name
    

class MaintenanceExpense(models.Model):

    shop = models.ForeignKey(
        Shop,
        on_delete=models.CASCADE
    )

    title = models.CharField(
        max_length=255
    )

    description = models.TextField()

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    maintenance_date = models.DateField()

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.title
    
