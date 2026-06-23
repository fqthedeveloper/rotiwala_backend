from firebase_admin import auth

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from .models import User
from .models import CustomerProfile
from .serializers import UserSerializer
from .models import ManagerProfile
from rest_framework import generics, status
from .serializers import ManagerSerializer
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.permissions import (
    IsSuperAdmin
)


class CustomerRegisterView(APIView):

    permission_classes = []

    def post(self, request):

        token = request.data.get("token")

        first_name = request.data.get(
            "first_name",
            ""
        )

        last_name = request.data.get(
            "last_name",
            ""
        )

        password = request.data.get(
            "password"
        )

        if not token:

            return Response(
                {
                    "error": "Firebase token required"
                },
                status=400
            )

        try:

            decoded = auth.verify_id_token(
                token,
                clock_skew_seconds=60
            )

            firebase_uid = decoded["uid"]

            phone = decoded.get(
                "phone_number"
            )

            if not phone:

                return Response(
                    {
                        "error": "Phone number not found"
                    },
                    status=400
                )

            if not password:

                return Response(
                    {
                        "error": "Password is required"
                    },
                    status=400
                )

            if len(password) < 6:

                return Response(
                    {
                        "error": "Password must be at least 6 characters"
                    },
                    status=400
                )

            if User.objects.filter(
                phone=phone
            ).exists():

                return Response(
                    {
                        "error": "Mobile number already registered"
                    },
                    status=400
                )

            user = User.objects.create_user(
                username=phone,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                password=password,
                firebase_uid=firebase_uid,
                role="customer",
                is_phone_verified=True
            )

            CustomerProfile.objects.create(
                user=user
            )

            refresh = RefreshToken.for_user(
                user
            )

            return Response(
                {
                    "message": "Registration successful",
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": UserSerializer(user).data
                }
            )

        except Exception as e:

            return Response(
                {
                    "error": str(e)
                },
                status=400
            )
            


class FirebaseLoginView(APIView):

    permission_classes = []

    def post(self, request):

        token = request.data.get("token")

        if not token:
            return Response(
                {
                    "error": "Firebase token required"
                },
                status=400
            )

        try:

            decoded = auth.verify_id_token(
                token,
                clock_skew_seconds=60
            )

            firebase_uid = decoded["uid"]
            phone = decoded.get("phone_number")

            if not phone:
                return Response(
                    {
                        "error": "Phone number not found"
                    },
                    status=400
                )

            try:

                user = User.objects.get(
                    phone=phone
                )

            except User.DoesNotExist:

                return Response(
                    {
                        "error": "This mobile number is not registered. Please register first."
                    },
                    status=400
                )

            if user.firebase_uid:

                if user.firebase_uid != firebase_uid:

                    return Response(
                        {
                            "error": "Account mismatch"
                        },
                        status=400
                    )

            else:

                user.firebase_uid = firebase_uid
                user.save()

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": UserSerializer(user).data
                }
            )

        except Exception as e:

            return Response(
                {
                    "error": str(e)
                },
                status=400
            )
            


class PasswordLoginView(APIView):

    permission_classes = []

    def post(self, request):

        phone = request.data.get("phone", "").strip()
        password = request.data.get("password", "").strip()

        # Validate input
        if not phone:
            return Response(
                {
                    "success": False,
                    "field": "phone",
                    "message": "Phone number is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not password:
            return Response(
                {
                    "success": False,
                    "field": "password",
                    "message": "Password is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check phone exists
        try:
            user = User.objects.get(phone=phone)

        except User.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "field": "phone",
                    "message": "This phone number is not registered."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Check account active
        if not user.is_active:
            return Response(
                {
                    "success": False,
                    "message": "Your account has been disabled. Please contact support."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Verify password
        auth_user = authenticate(
            username=user.username,
            password=password
        )

        if not auth_user:
            return Response(
                {
                    "success": False,
                    "field": "password",
                    "message": "Incorrect password. Please try again."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Generate JWT
        refresh = RefreshToken.for_user(auth_user)

        return Response(
            {
                "success": True,
                "message": f"Welcome back {auth_user.first_name or auth_user.username}!",
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(auth_user).data
            },
            status=status.HTTP_200_OK
        )


class SaveFCMTokenView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def post(self, request):

        token = request.data.get(
            "token"
        )

        request.user.fcm_token = token

        request.user.save()

        return Response({

            "message":
            "FCM Token Saved"
        })
        

class ManagerListView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def get(self, request):

        managers = User.objects.filter(
            role="manager"
        )

        serializer = ManagerSerializer(
                managers,
                many=True
            )

        return Response(
            serializer.data
        )


class CreateManagerView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def post(self, request):

        user = User.objects.create_user(
            username=request.data["phone"],
            phone=request.data["phone"],
            first_name=request.data["first_name"],
            last_name=request.data["last_name"],
            email=request.data.get(
                "email"
            ),
            password=request.data[
                "password"
            ],
            role="manager"
        )

        ManagerProfile.objects.create(
            user=user,
            full_name=f"{user.first_name} {user.last_name}",
            phone=user.phone
        )

        return Response({
            "message":
            "Manager Created"
        })
        
        

class ManagerDetailView(
    generics.RetrieveUpdateDestroyAPIView
):

    queryset = User.objects.filter(
        role="manager"
    )

    serializer_class = UserSerializer

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def update(
        self,
        request,
        *args,
        **kwargs
    ):

        manager = self.get_object()

        manager.first_name = request.data.get(
                "first_name"
            )

        manager.last_name = request.data.get(
                "last_name"
            )

        manager.phone = request.data.get(
                "phone"
            )

        manager.email = request.data.get(
                "email"
            )

        manager.username = manager.phone

        manager.save()

        profile = manager.manager_profile

        profile.full_name = (
            f"{manager.first_name} "
            f"{manager.last_name}"
        )

        profile.phone = manager.phone

        profile.shop_id = request.data.get(
                "shop_id"
            ) or None

        profile.save()

        password = request.data.get(
                "password"
            )

        if password:

            manager.set_password(
                password
            )

            manager.save()

        return Response({
            "message":
            "Manager Updated"
        })


class AssignManagerView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def post(self, request):

        manager_id = request.data.get(
                "manager_id"
            )

        shop_id = request.data.get(
                "shop_id"
            )

        profile = ManagerProfile.objects.get(
                user_id=manager_id
            )

        profile.shop_id = shop_id

        profile.save()

        return Response({
            "message":
            "Manager Assigned"
        })