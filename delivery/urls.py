# delivery/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DeliveryBoyProfileViewSet, DeliveryAssignmentViewSet,
    ParcelViewSet, DeliveryLocationViewSet,
    DeliveryStatisticsView, DeliveryDashboardView
)

router = DefaultRouter()
router.register(r'boys', DeliveryBoyProfileViewSet, basename='delivery-boys')
router.register(r'assignments', DeliveryAssignmentViewSet, basename='delivery-assignments')
router.register(r'parcels', ParcelViewSet, basename='parcels')
router.register(r'location', DeliveryLocationViewSet, basename='delivery-locations')

urlpatterns = [
    path('', include(router.urls)),
    path('statistics/', DeliveryStatisticsView.as_view(), name='delivery-statistics'),
    path('dashboard/', DeliveryDashboardView.as_view(), name='delivery-dashboard'),
]