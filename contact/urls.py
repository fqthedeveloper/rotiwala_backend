from django.urls import path

from .views import ContactInfoView, FeedbackCreateView

urlpatterns = [

    path(
        "",
        ContactInfoView.as_view()
    ),
    
    path(
        "feedback/",
        FeedbackCreateView.as_view()
    ),

]