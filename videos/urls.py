from django.urls import path
from .views import (
    # Marquee
    MarqueePublicView,
    MarqueeAdminListView,
    MarqueeAdminDetailView,
    # Testimonials
    TestimonialPublicView,
    TestimonialSubmitView,
    TestimonialAdminListView,
    TestimonialAdminUpdateView,
    # Videos
    VideoPublicView,
    VideoSubmitView,
    VideoAdminListView,
    VideoAdminUpdateView,
)

urlpatterns = [
    # ---------- MARQUEE ----------
    path('marquee/', MarqueePublicView.as_view(), name='marquee-public'),                    # GET – public
    path('marquee/admin/', MarqueeAdminListView.as_view(), name='marquee-admin-list'),       # GET, POST – admin
    path('marquee/admin/<int:pk>/', MarqueeAdminDetailView.as_view(), name='marquee-admin-detail'), # PUT, DELETE

    # ---------- TESTIMONIALS (CUSTOMER REVIEWS) ----------
    path('reviews/', TestimonialPublicView.as_view(), name='testimonial-public'),            # GET – public
    path('reviews/submit/', TestimonialSubmitView.as_view(), name='testimonial-submit'),     # POST – auth
    path('reviews/admin/', TestimonialAdminListView.as_view(), name='testimonial-admin-list'), # GET – admin
    path('reviews/admin/<int:pk>/', TestimonialAdminUpdateView.as_view(), name='testimonial-admin-update'), # PATCH

    # ---------- VIDEOS ----------
    path('videos/', VideoPublicView.as_view(), name='video-public'),                         # GET – public
    path('videos/submit/', VideoSubmitView.as_view(), name='video-submit'),                  # POST – auth
    path('videos/admin/', VideoAdminListView.as_view(), name='video-admin-list'),            # GET – admin (with filter)
    path('videos/admin/<int:pk>/', VideoAdminUpdateView.as_view(), name='video-admin-update'), # PATCH
]