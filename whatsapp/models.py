from django.db import models
from django.utils import timezone

class WhatsAppMessageLog(models.Model):
    """
    Log every outgoing WhatsApp message for auditing.
    """
    STATUS_CHOICES = (
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
    )
    template_name = models.CharField(max_length=100)
    recipient = models.CharField(max_length=20)  # phone number
    parameters = models.JSONField(default=dict, blank=True)  # the dynamic values used
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='sent')
    message_id = models.CharField(max_length=255, blank=True, null=True)  # from Meta
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.template_name} to {self.recipient} at {self.created_at}"