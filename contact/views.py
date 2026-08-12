# contact/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied
from django.utils import timezone

from .models import ContactInfo, Feedback
from .serializers import (
    ContactInfoSerializer,
    FeedbackSerializer,
    FeedbackAdminUpdateSerializer,
    FeedbackDetailSerializer,
)


class IsAdminOrManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['super_admin', 'manager']


# --- Public views ---

class ContactInfoView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        contact = ContactInfo.objects.filter(is_active=True).first()
        serializer = ContactInfoSerializer(contact)
        return Response(serializer.data)


class FeedbackCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = FeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Feedback submitted successfully"})


# --- Admin/Manager views ---

class FeedbackAdminListView(generics.ListAPIView):
    serializer_class = FeedbackDetailSerializer
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    def get_queryset(self):
        queryset = Feedback.objects.all()
        resolved = self.request.query_params.get('resolved')
        if resolved is not None:
            is_resolved = resolved.lower() == 'true'
            queryset = queryset.filter(is_resolved=is_resolved)
        return queryset


class FeedbackAdminDetailView(generics.RetrieveUpdateAPIView):
    queryset = Feedback.objects.all()
    permission_classes = [IsAuthenticated, IsAdminOrManager]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return FeedbackAdminUpdateSerializer
        return FeedbackDetailSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(FeedbackDetailSerializer(instance).data)