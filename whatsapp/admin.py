from django.contrib import admin
from .models import WhatsAppMessageLog

@admin.register(WhatsAppMessageLog)
class WhatsAppMessageLogAdmin(admin.ModelAdmin):
    list_display = ('template_name', 'recipient', 'status', 'created_at')
    list_filter = ('status', 'template_name')
    search_fields = ('recipient', 'message_id')
    readonly_fields = ('created_at', 'updated_at')