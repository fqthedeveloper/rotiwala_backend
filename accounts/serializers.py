from rest_framework import serializers
from .models import User, CustomerProfile, CustomerFlag, ManagerProfile


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


class CustomerFlagSerializer(serializers.ModelSerializer):
    flagged_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CustomerFlag
        fields = ['id', 'reason', 'created_at', 'flagged_by', 'flagged_by_name']
        read_only_fields = ['id', 'created_at', 'flagged_by']

    def get_flagged_by_name(self, obj):
        if obj.flagged_by:
            return f"{obj.flagged_by.first_name} {obj.flagged_by.last_name}".strip()
        return "System"


class CustomerProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='id')
    full_name = serializers.SerializerMethodField()
    flags = CustomerFlagSerializer(many=True, read_only=True, source='customer_flags')
    trust_score = serializers.IntegerField(source='customerprofile.trust_score')
    total_orders = serializers.IntegerField(source='customerprofile.total_orders')
    total_completed_orders = serializers.IntegerField(source='customerprofile.total_completed_orders')
    total_cancelled_orders = serializers.IntegerField(source='customerprofile.total_cancelled_orders')
    total_rejected_orders = serializers.IntegerField(source='customerprofile.total_rejected_orders')
    is_flagged = serializers.BooleanField(source='customerprofile.is_flagged')

    class Meta:
        model = User
        fields = [
            'user_id',
            'username',
            'first_name',
            'last_name',
            'full_name',          # <-- Added
            'phone',
            'email',
            'is_active',
            'trust_score',
            'total_orders',
            'total_completed_orders',
            'total_cancelled_orders',
            'total_rejected_orders',
            'is_flagged',
            'flags'
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


class CustomerListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    trust_score = serializers.IntegerField(source='customerprofile.trust_score')
    total_orders = serializers.IntegerField(source='customerprofile.total_orders')
    is_flagged = serializers.BooleanField(source='customerprofile.is_flagged')
    is_active = serializers.BooleanField()          # directly from User
    flag_count = serializers.IntegerField(source='customer_flags.count')

    class Meta:
        model = User
        fields = [
            'id', 'username', 'full_name', 'phone', 'email',
            'trust_score', 'total_orders', 'is_flagged', 'is_active', 'flag_count'
        ]

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or obj.username


class ManagerSerializer(serializers.ModelSerializer):
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

    def get_shop_name(self, obj):
        try:
            if obj.manager_profile.shop:
                return obj.manager_profile.shop.name
        except:
            pass
        return None