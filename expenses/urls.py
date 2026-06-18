from django.urls import path

from .views import *

urlpatterns = [

    path(
        "categories/",
        ExpenseCategoryListView.as_view()
    ),

    path(
        "category/<int:category_id>/items/",
        ExpenseMasterItemListView.as_view()
    ),

    path(
        "create/",
        CreateExpenseEntryView.as_view()
    ),

    path(
        "maintenance/create/",
        MaintenanceCreateView.as_view()
    ),
]