from django.contrib import admin
from .models import Shop, ShopOrderCapacityAudit
# Register your models here.
admin.site.register(Shop)
admin.site.register(ShopOrderCapacityAudit)
