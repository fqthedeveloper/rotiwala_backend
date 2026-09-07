from rest_framework import serializers

from .models import Shop
from accounts.models import ManagerProfile


class ManagerProfileSerializer(
    serializers.ModelSerializer
):

    username = serializers.CharField(
        source="user.username",
        read_only=True
    )

    email = serializers.EmailField(
        source="user.email",
        read_only=True
    )

    class Meta:
        model = ManagerProfile
        fields = [
            "id",
            "username",
            "email",
            "full_name",
            "phone",
            "photo"
        ]


class ShopSerializer(serializers.ModelSerializer):
    manager = serializers.SerializerMethodField()

    class Meta:
        model = Shop
        exclude = [
            "max_online_orders",
            "online_orders_manually_paused",
            "manual_pause_reason",
            "paused_at",
        ]

    def get_manager(self, obj):
        try:
            profile = obj.manager
            return ManagerProfileSerializer(profile).data
        except:
            return None