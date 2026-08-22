# delivery/serializers.py

from rest_framework import serializers
from .models import (
    DeliveryBoyProfile, DeliveryAssignment, Parcel,
    DeliveryLocation, WalkInTokenCounter
)


class DeliveryBoyProfileSerializer(serializers.ModelSerializer):
    # These are read-only fields from the User model
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    
    # Shop info
    shop = serializers.PrimaryKeyRelatedField(read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)
    
    # Current assignment (computed)
    current_assignment = serializers.SerializerMethodField()

    class Meta:
        model = DeliveryBoyProfile
        fields = [
            'id', 'user', 'user_id', 'user_phone',
            'shop', 'shop_name',
            'full_name',       # ← Now included in response
            'phone',           # ← Now included in response
            'photo',
            'is_online', 'is_available',
            'current_latitude', 'current_longitude', 'last_location_at',
            'total_deliveries', 'total_distance_km',
            'created_at', 'updated_at',
            'current_assignment'
        ]
        read_only_fields = [
            'total_deliveries', 'total_distance_km', 'created_at', 'updated_at',
            'is_online', 'is_available',
            'current_latitude', 'current_longitude', 'last_location_at',
            'user', 'user_id', 'user_phone', 'shop', 'shop_name',
        ]

    def get_current_assignment(self, obj):
        assignment = DeliveryAssignment.objects.filter(
            delivery_boy=obj,
            status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery']
        ).first()
        if assignment:
            return {
                'id': assignment.id,
                'order_number': assignment.order.order_number,
                'status': assignment.status,
                'customer_name': assignment.order.customer_name,
            }
        return None


class DeliveryBoyProfileDetailSerializer(DeliveryBoyProfileSerializer):
    """Extended with more details if needed."""
    pass


class ParcelSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    shop_code = serializers.CharField(source='shop.shop_code', read_only=True)

    class Meta:
        model = Parcel
        fields = [
            'id', 'order', 'order_number', 'shop', 'shop_code',
            'parcel_number', 'qr_token', 'status',
            'created_at', 'scanned_at', 'picked_up_at', 'delivered_at'
        ]
        read_only_fields = ['parcel_number', 'qr_token', 'created_at']


class DeliveryAssignmentSerializer(serializers.ModelSerializer):
    delivery_boy_name = serializers.CharField(source='delivery_boy.full_name', read_only=True)
    delivery_boy_phone = serializers.CharField(source='delivery_boy.phone', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    shop_code = serializers.CharField(source='shop.shop_code', read_only=True)
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True, allow_null=True)

    class Meta:
        model = DeliveryAssignment
        fields = [
            'id', 'order', 'order_number', 'parcel', 'parcel_number',
            'shop', 'shop_code', 'delivery_boy', 'delivery_boy_name',
            'delivery_boy_phone', 'assignment_mode', 'status',
            'assigned_at', 'accepted_at', 'picked_up_at',
            'out_for_delivery_at', 'delivered_at',
            'estimated_distance_km', 'actual_distance_km',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'assigned_at', 'created_at', 'updated_at',
            'estimated_distance_km', 'actual_distance_km'
        ]


class DeliveryLocationSerializer(serializers.ModelSerializer):
    delivery_boy_name = serializers.CharField(source='delivery_boy.full_name', read_only=True)

    class Meta:
        model = DeliveryLocation
        fields = [
            'id', 'delivery_boy', 'delivery_boy_name',
            'assignment', 'latitude', 'longitude',
            'accuracy', 'speed', 'recorded_at'
        ]
        read_only_fields = ['recorded_at']


class WalkInTokenCounterSerializer(serializers.ModelSerializer):
    shop_code = serializers.CharField(source='shop.shop_code', read_only=True)

    class Meta:
        model = WalkInTokenCounter
        fields = ['id', 'shop', 'shop_code', 'business_date', 'last_token']