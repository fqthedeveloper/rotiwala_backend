from django.contrib import admin

from .models import *

admin.site.register(
    User
)

admin.site.register(
    ManagerProfile
)
admin.site.register(
    CustomerProfile
)

admin.site.register(
    CustomerFlag
)

