from django.contrib import admin

from discounts import coupon_models

from .models import (
    Discount,
    DiscountUsage,
)


@admin.register(Discount)
class DiscountAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "shop",
        "apply_on",
        "discount_type",
        "value",
        "start_date",
        "end_date",
        "is_active",
    )

    list_filter = (
        "shop",
        "apply_on",
        "discount_type",
        "is_active",
    )

    search_fields = (
        "name",
    )


@admin.register(DiscountUsage)
class DiscountUsageAdmin(admin.ModelAdmin):

    list_display = (
        "discount",
        "customer",
        "order",
        "discount_amount",
        "created_at",
    )
    
    
@admin.register(coupon_models.Coupon)
class CouponAdmin(admin.ModelAdmin):

    list_display = (
        "code",
        "shop",
        "discount_type",
        "value",
        "start_date",
        "end_date",
        "status",
    )

    list_filter = (
        "shop",
        "discount_type",
        "status",
    )

    search_fields = (
        "code",
    )