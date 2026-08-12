# videos/admin.py
from django.contrib import admin
from .models import Marquee, Testimonial, Video

@admin.register(Marquee)
class MarqueeAdmin(admin.ModelAdmin):
    list_display = ('id', 'text', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('text',)


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    # Use fields that exist in your updated Testimonial model:
    # customer, role, text, rating, is_approved, created_at, updated_at
    list_display = ('id', 'customer', 'role', 'text_preview', 'rating', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'rating', 'created_at')
    search_fields = ('customer__username', 'customer__phone', 'text', 'role')
    actions = ['approve_selected']

    def text_preview(self, obj):
        return obj.text[:50] + '...' if len(obj.text) > 50 else obj.text
    text_preview.short_description = 'Text preview'

    def approve_selected(self, request, queryset):
        queryset.update(is_approved=True)
    approve_selected.short_description = "Approve selected testimonials"


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'video_type', 'status', 'submitted_by', 'created_at')
    list_filter = ('status', 'video_type', 'created_at')
    search_fields = ('title', 'description', 'submitted_by__username')
    actions = ['approve_videos', 'reject_videos']

    def approve_videos(self, request, queryset):
        for video in queryset:
            video.approve(request.user)
    approve_videos.short_description = "Approve selected videos"

    def reject_videos(self, request, queryset):
        for video in queryset:
            video.reject(request.user)
    reject_videos.short_description = "Reject selected videos"