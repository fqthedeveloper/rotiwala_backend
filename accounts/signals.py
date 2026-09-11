from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    User,
    CustomerProfile,
    ManagerProfile,
    PreparingStaffProfile,
)

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if not created:
        return

    if instance.role == "customer":
        CustomerProfile.objects.get_or_create(
            user=instance
        )
    elif instance.role == "manager":
        ManagerProfile.objects.get_or_create(
            user=instance
        )
    elif instance.role == "preparing_staff":
        PreparingStaffProfile.objects.get_or_create(
            user=instance,
            defaults={"full_name": instance.get_full_name() or instance.username}
        )