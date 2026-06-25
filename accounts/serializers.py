from rest_framework import serializers
from .models import User
from .models import CustomerProfile
from .models import ManagerProfile



class UserSerializer(serializers.ModelSerializer):

    shop_id = serializers.SerializerMethodField()
    shop_name = serializers.SerializerMethodField()

    class Meta:
        model = User

        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "phone",
            "email",
            "role",
            "is_phone_verified",
            "shop_id",
            "shop_name",
        ]

    def get_shop_id(self, obj):
        try:
            return obj.manager_profile.shop.id
        except Exception:
            return None

    def get_shop_name(self, obj):
        try:
            return obj.manager_profile.shop.name
        except Exception:
            return None


class CustomerProfileSerializer(serializers.ModelSerializer):

    user = UserSerializer()

    class Meta:
        model = CustomerProfile
        fields = "__all__"



class ManagerSerializer(
    serializers.ModelSerializer
):

    shop_name = serializers.SerializerMethodField()

    class Meta:

        model = User

        fields = [
            "id",
            "first_name",
            "last_name",
            "phone",
            "email",
            "role",
            "shop_name",
        ]

    def get_shop_name(
        self,
        obj
    ):

        try:

            if obj.manager_profile.shop:
                return obj.manager_profile.shop.name

        except:
            pass

        return None