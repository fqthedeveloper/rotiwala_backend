from django.contrib import admin
from .models import DeliveryBoyProfile, DeliveryAssignment, Parcel, DeliveryLocation, WalkInTokenCounter, DeliveryBoyOTP
# Register your models here.


admin.site.register(DeliveryBoyProfile)
admin.site.register(DeliveryAssignment)
admin.site.register(Parcel)
admin.site.register(DeliveryLocation)
admin.site.register(WalkInTokenCounter)
admin.site.register(DeliveryBoyOTP)