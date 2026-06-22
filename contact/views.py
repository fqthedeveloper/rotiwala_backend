from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from .models import ContactInfo

from .serializers import (
    ContactInfoSerializer, 
    FeedbackSerializer,
)


class ContactInfoView(APIView):

    permission_classes = [
        AllowAny
    ]

    def get(self, request):

        contact = (
            ContactInfo.objects
            .filter(
                is_active=True
            )
            .first()
        )

        serializer = (
            ContactInfoSerializer(
                contact
            )
        )

        return Response(
            serializer.data
        )
        

class FeedbackCreateView(
    APIView
):

    permission_classes = [
        AllowAny
    ]

    def post(
        self,
        request
    ):

        serializer = (
            FeedbackSerializer(
                data=request.data
            )
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save()

        return Response(
            {
                "message":
                "Feedback submitted successfully"
            }
        )