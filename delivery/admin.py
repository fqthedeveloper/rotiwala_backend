from django.contrib import admin
from django.utils.html import format_html
from .models import (
    DeliveryBoyProfile, DeliveryAssignment, Parcel,
    DeliveryLocation, WalkInTokenCounter, DeliveryBoyOTP
)


# ─────────────────────────────────────────────────────────────
#  DELIVERY ASSIGNMENT  (with UPI payment proof)
# ─────────────────────────────────────────────────────────────

@admin.register(DeliveryAssignment)
class DeliveryAssignmentAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'order_number_link', 'delivery_boy', 'shop', 'status',
        'payment_mode', 'collected_amount', 'is_paid',
        'payment_proof_thumbnail', 'payment_collected_at',
    ]
    list_filter = ['status', 'is_paid', 'payment_mode', 'shop']
    search_fields = [
        'order__order_number', 'delivery_boy__full_name', 'delivery_boy__phone'
    ]
    readonly_fields = [
        'payment_proof_preview', 'assigned_at', 'accepted_at',
        'picked_up_at', 'out_for_delivery_at', 'delivered_at',
        'created_at', 'updated_at',
    ]

    fieldsets = (
        ('Assignment Info', {
            'fields': ('order', 'parcel', 'shop', 'delivery_boy', 'assignment_mode', 'status')
        }),
        ('Payment Collection', {
            'fields': (
                'is_paid', 'payment_mode', 'collected_amount',
                'payment_collected_at', 'payment_notes',
                'payment_proof', 'payment_proof_preview',
            ),
            'description': 'Payment proof photo uploaded by the delivery boy after UPI collection.',
        }),
        ('Distance', {
            'fields': ('estimated_distance_km', 'actual_distance_km'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': (
                'assigned_at', 'accepted_at', 'picked_up_at',
                'out_for_delivery_at', 'delivered_at', 'created_at', 'updated_at'
            ),
            'classes': ('collapse',),
        }),
    )

    # ── list display helpers ──────────────────────────────────

    def order_number_link(self, obj):
        url = f'/admin/orders/order/{obj.order_id}/change/'
        return format_html(
            '<a href="{}">{}</a>', url, obj.order.order_number
        )
    order_number_link.short_description = 'Order'
    order_number_link.admin_order_field = 'order__order_number'

    def payment_proof_thumbnail(self, obj):
        """Small thumbnail in list view - click to open full image."""
        if obj.payment_proof:
            return format_html(
                '<a href="{}" target="_blank" title="Click to view full payment proof">'
                '<img src="{}" style="height:48px; width:48px; object-fit:cover; '
                'border-radius:6px; border:2px solid #10b981;" />'
                '</a>',
                obj.payment_proof.url, obj.payment_proof.url
            )
        return format_html('<span style="color:#aaa; font-size:11px;">No proof</span>')
    payment_proof_thumbnail.short_description = '📷 Proof'

    # ── detail view helpers ───────────────────────────────────

    def payment_proof_preview(self, obj):
        """Large full preview in detail edit view."""
        if obj.payment_proof:
            return format_html(
                '<div style="margin:12px 0; padding:16px; background:#f0fdf4; '
                'border:2px solid #10b981; border-radius:10px; display:inline-block; max-width:420px;">'
                '  <p style="margin:0 0 10px 0; font-weight:bold; color:#065f46; font-size:14px;">'
                '    ✅ Payment Proof Photo Uploaded'
                '  </p>'
                '  <a href="{}" target="_blank">'
                '    <img src="{}" style="max-width:380px; max-height:400px; object-fit:contain; '
                '    border-radius:8px; display:block; box-shadow:0 2px 8px rgba(0,0,0,0.15);" />'
                '  </a>'
                '  <p style="margin:10px 0 0 0; font-size:12px; color:#374151;">'
                '    📎 <a href="{}" target="_blank" style="color:#059669;">Click here to open full size</a>'
                '  </p>'
                '</div>',
                obj.payment_proof.url,
                obj.payment_proof.url,
                obj.payment_proof.url,
            )
        return format_html(
            '<div style="padding:12px 16px; background:#fef2f2; border:1px dashed #ef4444; '
            'border-radius:8px; color:#b91c1c; font-size:13px;">'
            '  ❌ No payment proof photo has been uploaded yet.'
            '</div>'
        )
    payment_proof_preview.short_description = 'Payment Proof Preview'


# ─────────────────────────────────────────────────────────────
#  OTHER MODELS
# ─────────────────────────────────────────────────────────────

@admin.register(DeliveryBoyProfile)
class DeliveryBoyProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'full_name', 'phone', 'shop', 'is_online', 'is_available', 'total_deliveries']
    list_filter = ['shop', 'is_online', 'is_available']
    search_fields = ['full_name', 'phone']


admin.site.register(Parcel)
admin.site.register(DeliveryLocation)
admin.site.register(WalkInTokenCounter)
admin.site.register(DeliveryBoyOTP)