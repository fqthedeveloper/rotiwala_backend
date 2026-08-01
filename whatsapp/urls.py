# whatsapp/urls.py
from django.urls import path
from .views import index, webhook

urlpatterns = [
    path('', index, name='whatsapp_index'),
    path('webhook/', webhook, name='whatsapp_webhook'),
]