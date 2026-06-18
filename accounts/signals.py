from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import (
    User,
    CustomerProfile,
    ManagerProfile
)


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):

    if not created:
        return

    if instance.role == "customer":

        CustomerProfile.objects.create(
            user=instance
        )

    elif instance.role == "manager":

        ManagerProfile.objects.create(
            user=instance
        )