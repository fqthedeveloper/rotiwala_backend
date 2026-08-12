from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import User 

User = get_user_model()

class Marquee(models.Model):
    """Marquee – scrolling text for announcements"""
    text = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.text[:50]


class Testimonial(models.Model):
    """Customer review – displayed in reviews grid"""
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='testimonials')
    role = models.CharField(max_length=100, blank=True, help_text="e.g. 'Customer'")
    text = models.TextField()
    rating = models.PositiveSmallIntegerField(
        default=5,
        choices=[(i, i) for i in range(1, 6)]
    )
    is_approved = models.BooleanField(default=False)  # from super admin
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer} - {self.text[:50]}"

    def approve(self):
        self.is_approved = True
        self.save()


class Video(models.Model):
    """Video – supports YouTube embed or uploaded MP4"""
    VIDEO_TYPES = (
        ('youtube', 'YouTube'),
        ('upload', 'Uploaded MP4'),
    )
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    video_type = models.CharField(max_length=20, choices=VIDEO_TYPES, default='upload')
    youtube_url = models.URLField(blank=True, null=True, help_text="YouTube URL")
    video_file = models.FileField(upload_to='videos/', blank=True, null=True)
    poster = models.ImageField(upload_to='video_posters/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='videos')
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='reviewed_videos')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def embed_url(self):
        if self.video_type == 'youtube' and self.youtube_url:
            import re
            pattern = r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([a-zA-Z0-9_-]{11})'
            match = re.search(pattern, self.youtube_url)
            if match:
                return f"https://www.youtube.com/embed/{match.group(1)}"
        return None

    @property
    def video_src(self):
        if self.video_type == 'upload' and self.video_file:
            return self.video_file.url
        return None

    def approve(self, reviewer):
        self.status = 'approved'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()

    def reject(self, reviewer):
        self.status = 'rejected'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()