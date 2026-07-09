from django.urls import path
from .views import (
    DiscountListCreateView,
    DiscountDetailView,
    DiscountDashboardView,
)

urlpatterns = [
    # List & Create discounts
    path("", DiscountListCreateView.as_view()),

    # Retrieve / Update / Delete a single discount
    path("<int:pk>/", DiscountDetailView.as_view()),

    # Dashboard summary
    path("dashboard/", DiscountDashboardView.as_view()),
]