from django.contrib import admin

from .models import ContactInfo


@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):

    list_display = (
        "company_name",
        "phone",
        "email",
        "is_active",
    )