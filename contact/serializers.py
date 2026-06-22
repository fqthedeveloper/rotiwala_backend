from rest_framework import serializers

from .models import ContactInfo, Feedback


class ContactInfoSerializer(
    serializers.ModelSerializer
):

    class Meta:

        model = ContactInfo

        fields = "__all__"
        

class FeedbackSerializer(
    serializers.ModelSerializer
):

    class Meta:

        model = Feedback

        fields = "__all__"