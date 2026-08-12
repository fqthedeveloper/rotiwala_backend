from django.contrib import admin

from .models import ContactInfo, Feedback


@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):
    list_display = (
        "company_name",
        "phone",
        "email",
        "is_active",
    )


admin.site.register(Feedback)