from django.contrib import admin

from .models import *

admin.site.register(
    ExpenseCategory
)

admin.site.register(
    ExpenseMasterItem
)

admin.site.register(
    ExpenseEntry
)

admin.site.register(
    ExpenseItemEntry
)

admin.site.register(
    MaintenanceExpense
)