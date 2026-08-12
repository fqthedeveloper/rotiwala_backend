from rest_framework import serializers
from .models import Marquee, Testimonial, Video

# ---------- MARQUEE ----------
class MarqueeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marquee
        fields = ['id', 'text', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


# ---------- TESTIMONIALS ----------
class TestimonialSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.get_full_name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, default=None)

    class Meta:
        model = Testimonial
        fields = ['id', 'customer', 'customer_name', 'customer_phone', 'role', 'text', 'rating', 'is_approved', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at', 'customer']


class TestimonialSubmitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = ['role', 'text', 'rating']

    def create(self, validated_data):
        validated_data['customer'] = self.context['request'].user
        return super().create(validated_data)


class TestimonialAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = ['is_approved']


# ---------- VIDEOS ----------
class VideoSerializer(serializers.ModelSerializer):
    submitted_by_name = serializers.CharField(source='submitted_by.get_full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    embed_url = serializers.SerializerMethodField()
    video_src = serializers.SerializerMethodField()

    class Meta:
        model = Video
        fields = [
            'id', 'title', 'description', 'video_type', 'youtube_url', 'video_file',
            'poster', 'status', 'status_display', 'submitted_by', 'submitted_by_name',
            'embed_url', 'video_src', 'created_at', 'updated_at'
        ]
        read_only_fields = ['submitted_by', 'reviewed_by', 'reviewed_at', 'created_at', 'updated_at', 'status']

    def get_embed_url(self, obj):
        return obj.embed_url

    def get_video_src(self, obj):
        return obj.video_src


class VideoSubmitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ['title', 'description', 'video_type', 'youtube_url', 'video_file', 'poster']

    def create(self, validated_data):
        validated_data['submitted_by'] = self.context['request'].user
        return super().create(validated_data)


class VideoAdminUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Video
        fields = ['status']