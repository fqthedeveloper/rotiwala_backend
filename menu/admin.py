from django.contrib import admin
from django.utils.html import format_html
from .models import MenuCategory, MenuItem


@admin.register(MenuCategory)
class MenuCategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'image_thumbnail', 'name', 'category', 'shop', 'base_price', 'is_available', 'is_active', 'created_at')
    list_filter = ('is_available', 'is_active', 'category', 'shop')
    search_fields = ('name', 'description')
    readonly_fields = ('image_preview', 'created_at')

    def image_thumbnail(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 44px; height: 44px; object-fit: contain; border-radius: 6px; background: #FFF;" />',
                obj.image.url
            )
        return format_html('<span style="color: #999;">No image</span>')
    image_thumbnail.short_description = "Image"

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 250px; object-fit: contain; border-radius: 8px; border: 1px solid #ddd; background: #FFF; padding: 4px;" /><br>'
                '<small style="color: #666;">File: {}</small>',
                obj.image.url,
                obj.image.name
            )
        return "No image uploaded"
    image_preview.short_description = "Image Preview"

