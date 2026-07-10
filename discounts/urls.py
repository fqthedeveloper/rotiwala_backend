from django.urls import path
from .views import (
    DiscountListCreateView,
    DiscountDetailView,
    DiscountDashboardView,
    UsageSummaryView,
    UsageListView,
)

urlpatterns = [
    # List & Create discounts
    path("", DiscountListCreateView.as_view()),

    # Retrieve / Update / Delete a single discount
    path("<int:pk>/", DiscountDetailView.as_view()),

    # Dashboard summary
    path("dashboard/", DiscountDashboardView.as_view()),
    
    path('usage-summary/', UsageSummaryView.as_view(), name='usage-summary'),
    path('usage-list/', UsageListView.as_view(), name='usage-list'),
]