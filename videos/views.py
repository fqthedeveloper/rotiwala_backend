from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Marquee, Testimonial, Video
from .serializers import (
    MarqueeSerializer,
    TestimonialSerializer,
    TestimonialSubmitSerializer,
    TestimonialAdminUpdateSerializer,
    VideoSerializer,
    VideoSubmitSerializer,
    VideoAdminUpdateSerializer,
)

# =================================================================
# 1. MARQUEE – public (active) and admin CRUD
# =================================================================
class MarqueePublicView(generics.ListAPIView):
    """Public: only active marquee items (for homepage)"""
    serializer_class = MarqueeSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Marquee.objects.filter(is_active=True)


class MarqueeAdminListView(generics.ListCreateAPIView):
    """Admin: list all marquee items, create new"""
    queryset = Marquee.objects.all()
    serializer_class = MarqueeSerializer
    permission_classes = [permissions.IsAdminUser]


class MarqueeAdminDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Admin: update or delete a marquee item"""
    queryset = Marquee.objects.all()
    serializer_class = MarqueeSerializer
    permission_classes = [permissions.IsAdminUser]


# =================================================================
# 2. TESTIMONIALS (Customer Reviews)
# =================================================================
class TestimonialPublicView(generics.ListAPIView):
    """Public: approved testimonials (for homepage reviews grid)"""
    serializer_class = TestimonialSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Testimonial.objects.filter(is_approved=True)


class TestimonialSubmitView(generics.CreateAPIView):
    """Authenticated: submit a testimonial (pending approval)"""
    serializer_class = TestimonialSubmitSerializer
    permission_classes = [permissions.IsAuthenticated]


class TestimonialAdminListView(generics.ListAPIView):
    """Admin: list all testimonials"""
    serializer_class = TestimonialSerializer
    permission_classes = [permissions.IsAdminUser]
    queryset = Testimonial.objects.all()


class TestimonialAdminUpdateView(generics.UpdateAPIView):
    """Admin: approve/reject testimonial"""
    queryset = Testimonial.objects.all()
    serializer_class = TestimonialAdminUpdateSerializer
    permission_classes = [permissions.IsAdminUser]

    def update(self, request, *args, **kwargs):
        testimonial = self.get_object()
        is_approved = request.data.get('is_approved')
        if is_approved is not None:
            testimonial.is_approved = is_approved
            testimonial.save()
        return Response(TestimonialSerializer(testimonial).data)


# =================================================================
# 3. VIDEOS
# =================================================================
class VideoPublicView(generics.ListAPIView):
    """Public: approved videos (for homepage slideshow)"""
    serializer_class = VideoSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return Video.objects.filter(status='approved')


class VideoSubmitView(generics.CreateAPIView):
    """Authenticated: submit a video (pending approval)"""
    serializer_class = VideoSubmitSerializer
    permission_classes = [permissions.IsAuthenticated]


class VideoAdminListView(generics.ListAPIView):
    """Admin: list all videos with optional status filter"""
    serializer_class = VideoSerializer
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        queryset = Video.objects.all()
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return queryset


class VideoAdminUpdateView(generics.UpdateAPIView):
    """Admin: approve/reject video"""
    queryset = Video.objects.all()
    serializer_class = VideoAdminUpdateSerializer
    permission_classes = [permissions.IsAdminUser]

    def update(self, request, *args, **kwargs):
        video = self.get_object()
        new_status = request.data.get('status')
        if new_status not in ['approved', 'rejected']:
            return Response({'error': 'Invalid status'}, status=status.HTTP_400_BAD_REQUEST)
        if new_status == 'approved':
            video.approve(request.user)
        else:
            video.reject(request.user)
        return Response(VideoSerializer(video).data)