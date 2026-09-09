# delivery/serializers.py

from rest_framework import serializers
from .models import DeliveryBoyProfile, DeliveryAssignment, Parcel, DeliveryLocation, WalkInTokenCounter, DeliveryBoyOTP
from accounts.models import User
from django.contrib.auth import authenticate
from django.utils import timezone


class DeliveryBoyProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    user_phone = serializers.CharField(source='user.phone', read_only=True)
    shop = serializers.PrimaryKeyRelatedField(read_only=True)
    shop_name = serializers.CharField(source='shop.name', read_only=True)

    # NEW - Return list of current assignments
    current_assignments = serializers.SerializerMethodField()
    active_order_count = serializers.IntegerField(read_only=True)
    has_capacity = serializers.BooleanField(read_only=True)

    class Meta:
        model = DeliveryBoyProfile
        fields = [
            'id', 'user', 'user_id', 'user_phone',
            'shop', 'shop_name',
            'full_name', 'phone', 'photo',
            'is_online', 'is_available', 'max_active_orders',
            'active_order_count', 'has_capacity',
            'current_latitude', 'current_longitude', 'last_location_at',
            'total_deliveries', 'total_distance_km',
            'created_at', 'updated_at',
            'current_assignments'  # <-- changed from current_assignment
        ]
        read_only_fields = [
            'total_deliveries', 'total_distance_km', 'created_at', 'updated_at',
            'is_online', 'is_available', 'active_order_count', 'has_capacity',
            'current_latitude', 'current_longitude', 'last_location_at',
            'user', 'user_id', 'user_phone', 'shop', 'shop_name',
        ]

    def get_current_assignments(self, obj):
        assignments = DeliveryAssignment.objects.filter(
            delivery_boy=obj,
            status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery']
        )
        return [
            {
                'id': a.id,
                'order_id': a.order_id, # <-- Ensure this is here
                'order_number': a.order.order_number,
                'status': a.status,
                'customer_name': a.order.customer_name,
            } for a in assignments
        ]


class DeliveryBoyProfileDetailSerializer(DeliveryBoyProfileSerializer):
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


# delivery/serializers.py

class DeliveryAssignmentSerializer(serializers.ModelSerializer):
    delivery_boy_name = serializers.CharField(source='delivery_boy.full_name', read_only=True)
    delivery_boy_phone = serializers.CharField(source='delivery_boy.phone', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    shop_code = serializers.CharField(source='shop.shop_code', read_only=True)
    parcel_number = serializers.CharField(source='parcel.parcel_number', read_only=True, allow_null=True)

    # 🔹 ADD THESE CUSTOMER & DELIVERY FIELDS FROM ORDER
    customer_name = serializers.CharField(source='order.customer_name', read_only=True)
    customer_phone = serializers.CharField(source='order.customer_phone', read_only=True)
    delivery_address = serializers.CharField(source='order.delivery_address', read_only=True)
    delivery_latitude = serializers.CharField(source='order.delivery_latitude', read_only=True, allow_null=True)
    delivery_longitude = serializers.CharField(source='order.delivery_longitude', read_only=True, allow_null=True)
    total_amount = serializers.CharField(source='order.total_amount', read_only=True)
    payment_method = serializers.CharField(source='order.payment_method', read_only=True)
    payment_status = serializers.CharField(source='order.payment_status', read_only=True)

    class Meta:
        model = DeliveryAssignment
        fields = [
            'id', 'order', 'order_number', 'parcel', 'parcel_number',
            'shop', 'shop_code', 'delivery_boy', 'delivery_boy_name',
            'delivery_boy_phone', 'assignment_mode', 'status',
            # 🔹 INCLUDE NEW FIELDS IN FIELDS ARRAY
            'customer_name', 'customer_phone', 'delivery_address',
            'delivery_latitude', 'delivery_longitude',
            'total_amount', 'payment_method', 'payment_status',
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
        
        

# ============================================================
# NEW: Auth Serializers
# ============================================================

class DeliveryBoyLoginSerializer(serializers.Serializer):
    phone = serializers.CharField()
    password = serializers.CharField(required=False, allow_blank=True)
    otp = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        phone = attrs.get('phone')
        password = attrs.get('password')
        otp = attrs.get('otp')

        if not phone:
            raise serializers.ValidationError("Phone number is required.")

        # OTP login
        if otp:
            try:
                otp_obj = DeliveryBoyOTP.objects.filter(phone=phone, used=False).latest('created_at')
                if otp_obj.expires_at < timezone.now():
                    raise serializers.ValidationError("OTP has expired.")
                if otp_obj.otp_code != otp:
                    raise serializers.ValidationError("Invalid OTP.")
            except DeliveryBoyOTP.DoesNotExist:
                raise serializers.ValidationError("Invalid OTP.")
            attrs['otp_obj'] = otp_obj
            return attrs

        # Password login
        if not password:
            raise serializers.ValidationError("Password or OTP is required.")

        # Find user by phone
        try:
            user = User.objects.get(phone=phone, role='delivery_boy')
        except User.DoesNotExist:
            raise serializers.ValidationError("No delivery boy found with this phone number.")

        user = authenticate(username=user.username, password=password)
        if not user:
            raise serializers.ValidationError("Invalid password.")
        attrs['user'] = user
        return attrs