# contact/serializers.py
from rest_framework import serializers
from .models import ContactInfo, Feedback
from django.utils import timezone


class ContactInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContactInfo
        fields = "__all__"


class FeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = "__all__"


class FeedbackAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Feedback
        fields = ['admin_reply', 'is_resolved']

    def update(self, instance, validated_data):
        instance.admin_reply = validated_data.get('admin_reply', instance.admin_reply)
        instance.is_resolved = validated_data.get('is_resolved', instance.is_resolved)
        if instance.is_resolved and not instance.resolved_at:
            instance.resolved_at = timezone.now()
            instance.resolved_by = self.context['request'].user
        elif not instance.is_resolved:
            instance.resolved_at = None
            instance.resolved_by = None
        instance.save()
        return instance


class FeedbackDetailSerializer(serializers.ModelSerializer):
    resolved_by_name = serializers.CharField(source='resolved_by.get_full_name', read_only=True, default=None)

    class Meta:
        model = Feedback
        fields = [
            'id', 'name', 'email', 'phone', 'subject', 'message',
            'admin_reply', 'is_resolved', 'resolved_at', 'resolved_by_name',
            'created_at', 'updated_at'
        ]