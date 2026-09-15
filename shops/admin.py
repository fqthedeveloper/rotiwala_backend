from django.contrib import admin
from django.utils.html import format_html
from .models import Shop, ShopOrderCapacityAudit


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'name', 'shop_code', 'phone', 'is_active',
        'upi_id', 'upi_qr_preview', 'updated_at'
    ]
    list_filter = ['is_active', 'delivery_assignment_mode']
    search_fields = ['name', 'shop_code', 'phone', 'upi_id']
    readonly_fields = ['upi_qr_large_preview', 'shop_code', 'created_at', 'updated_at']

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'shop_code', 'phone', 'email', 'address', 'logo', 'banner', 'is_active')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude')
        }),
        ('UPI / Payment Settings', {
            'fields': ('upi_id', 'upi_qr_image', 'upi_qr_large_preview'),
            'description': (
                'Upload your shop UPI QR code image here. '
                'If not uploaded, a dynamic QR will be auto-generated for the delivery boy using the UPI ID.'
            ),
        }),
        ('Delivery Settings', {
            'fields': (
                'delivery_enabled', 'delivery_assignment_mode',
                'delivery_radius_km', 'delivery_fee',
                'free_delivery_min_order', 'minimum_delivery_order',
            )
        }),
        ('Opening Hours', {
            'fields': ('opening_time', 'closing_time')
        }),
        ('Online Order Capacity', {
            'fields': ('max_online_orders', 'online_orders_manually_paused', 'manual_pause_reason', 'paused_at')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def upi_qr_preview(self, obj):
        """Small thumbnail in list view."""
        if obj.upi_qr_image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="height:45px; width:45px; object-fit:contain; border:1px solid #ddd; border-radius:4px; background:#fff;" />'
                '</a>',
                obj.upi_qr_image.url, obj.upi_qr_image.url
            )
        return format_html(
            '<span style="color:#aaa; font-size:11px;">No QR</span>'
        )
    upi_qr_preview.short_description = 'UPI QR'

    def upi_qr_large_preview(self, obj):
        """Large preview in detail view with UPI details."""
        if obj.upi_qr_image:
            return format_html(
                '<div style="margin:10px 0; padding:15px; background:#f9f9f9; border:1px solid #ddd; border-radius:8px; display:inline-block;">'
                '  <p style="margin:0 0 8px 0; font-weight:bold; color:#333;">Current UPI QR Code</p>'
                '  <a href="{}" target="_blank">'
                '    <img src="{}" style="max-height:250px; max-width:250px; object-fit:contain; border-radius:6px; display:block;" />'
                '  </a>'
                '  <p style="margin:8px 0 0 0; font-size:12px; color:#666;">Click image to open full size &bull; UPI ID: <strong>{}</strong></p>'
                '</div>',
                obj.upi_qr_image.url,
                obj.upi_qr_image.url,
                obj.upi_id or 'Not set'
            )
        elif obj.upi_id:
            dynamic_qr = (
                f"https://api.qrserver.com/v1/create-qr-code/?size=250x250"
                f"&data=upi://pay?pa={obj.upi_id}%26pn={obj.name}%26cu=INR"
            )
            return format_html(
                '<div style="margin:10px 0; padding:15px; background:#fff8e1; border:1px solid #ffc107; border-radius:8px; display:inline-block;">'
                '  <p style="margin:0 0 8px 0; font-weight:bold; color:#e65100;">⚠️ No custom QR uploaded — showing auto-generated QR</p>'
                '  <img src="{}" style="max-height:200px; max-width:200px; object-fit:contain; border-radius:6px; display:block;" />'
                '  <p style="margin:8px 0 0 0; font-size:12px; color:#666;">UPI ID: <strong>{}</strong> &bull; Upload a custom QR image above for better quality.</p>'
                '</div>',
                dynamic_qr,
                obj.upi_id
            )
        return format_html(
            '<span style="color:#aaa;">No UPI QR image uploaded and no UPI ID set. '
            'Please fill in the UPI ID and optionally upload a QR image.</span>'
        )
    upi_qr_large_preview.short_description = 'UPI QR Preview'


@admin.register(ShopOrderCapacityAudit)
class ShopOrderCapacityAuditAdmin(admin.ModelAdmin):
    list_display = ['id', 'shop', 'action', 'old_value', 'new_value', 'reason', 'manager', 'created_at']
    list_filter = ['shop', 'action']
    search_fields = ['shop__name', 'manager__phone']
    readonly_fields = ['created_at']
