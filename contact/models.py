from django.db import models


class ContactInfo(models.Model):

    company_name = models.CharField(
        max_length=200
    )

    phone = models.CharField(
        max_length=20
    )

    whatsapp = models.CharField(
        max_length=20
    )

    email = models.EmailField()

    address = models.TextField()

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7
    )

    opening_time = models.TimeField()

    closing_time = models.TimeField()

    facebook = models.URLField(
        blank=True
    )

    instagram = models.URLField(
        blank=True
    )

    youtube = models.URLField(
        blank=True
    )

    is_active = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.company_name
    

class Feedback(models.Model):

    name = models.CharField(
        max_length=200
    )

    email = models.EmailField(
        blank=True
    )

    phone = models.CharField(
        max_length=20
    )

    subject = models.CharField(
        max_length=200
    )

    message = models.TextField()

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.name