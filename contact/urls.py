# contact/urls.py
from django.urls import path
from .views import (
    ContactInfoView,
    FeedbackCreateView,
    FeedbackAdminListView,
    FeedbackAdminDetailView,
)

urlpatterns = [
    # Public endpoints
    path('', ContactInfoView.as_view(), name='contact-info'),
    path('feedback/', FeedbackCreateView.as_view(), name='feedback-create'),

    # Admin/Manager endpoints
    path('admin/feedback/', FeedbackAdminListView.as_view(), name='feedback-admin-list'),
    path('admin/feedback/<int:pk>/', FeedbackAdminDetailView.as_view(), name='feedback-admin-detail'),
]