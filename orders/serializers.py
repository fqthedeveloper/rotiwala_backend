from rest_framework import serializers

from .models import (
    Order,
    OrderItem,
    WalkInCart,
    WalkInCartItem,
)


# ==========================================
# ORDER SERIALIZERS
# ==========================================

class OrderItemSerializer(serializers.ModelSerializer):

    class Meta:

        model = OrderItem

        fields = "__all__"


class OrderSerializer(serializers.ModelSerializer):

    items = OrderItemSerializer(
        many=True,
        read_only=True
    )

    customer_name = serializers.SerializerMethodField()

    customer_phone = serializers.SerializerMethodField()

    pickup_display = serializers.SerializerMethodField()

    shop_details = serializers.SerializerMethodField()

    delivery_details = serializers.SerializerMethodField()

    customer_is_flagged = serializers.SerializerMethodField()

    customer_trust_score = serializers.SerializerMethodField()

    customer_flag_reasons = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = "__all__"

    def get_customer_name(self, obj):

        if obj.customer_name:
            return obj.customer_name

        if obj.customer:
            return (
                obj.customer.get_full_name()
                or obj.customer.username
            )

        return None

    def get_customer_phone(self, obj):

        if obj.customer_phone:
            return obj.customer_phone

        if obj.customer:
            return obj.customer.phone

        return None

    def get_pickup_display(self, obj):

        if obj.pickup_type == "instant":

            return "Prepare Immediately"

        if obj.pickup_time:

            return obj.pickup_time.strftime(
                "%d %b %Y %I:%M %p"
            )

        return None

    def get_shop_details(self, obj):
        if not obj.shop:
            return None
        return {
            "id": obj.shop.id,
            "name": obj.shop.name,
            "address": obj.shop.address,
            "phone": getattr(obj.shop, "phone", None),
            "latitude": float(obj.shop.latitude) if obj.shop.latitude is not None else None,
            "longitude": float(obj.shop.longitude) if obj.shop.longitude is not None else None,
            "opening_time": str(obj.shop.opening_time) if getattr(obj.shop, "opening_time", None) else None,
            "closing_time": str(obj.shop.closing_time) if getattr(obj.shop, "closing_time", None) else None,
        }

    def get_delivery_details(self, obj):
        try:
            da = getattr(obj, "delivery_assignment", None)
            if da and da.delivery_boy:
                boy = da.delivery_boy
                return {
                    "status": da.status,
                    "delivery_boy_name": boy.full_name or (boy.user.get_full_name() if boy.user else ""),
                    "delivery_boy_phone": boy.phone or (boy.user.phone if boy.user else ""),
                    "latitude": float(boy.current_latitude) if boy.current_latitude is not None else None,
                    "longitude": float(boy.current_longitude) if boy.current_longitude is not None else None,
                }
        except Exception:
            pass
        return None

    def _resolve_customer(self, obj):
        if obj.customer:
            return obj.customer
        if obj.customer_phone:
            from accounts.models import User
            return User.objects.filter(phone=obj.customer_phone, role="customer").first()
        return None

    def get_customer_is_flagged(self, obj):
        customer = self._resolve_customer(obj)
        if customer:
            from accounts.models import CustomerProfile
            prof = CustomerProfile.objects.filter(user=customer).first()
            if prof:
                return bool(prof.is_flagged)
        return False

    def get_customer_trust_score(self, obj):
        customer = self._resolve_customer(obj)
        if customer:
            from accounts.models import CustomerProfile
            prof = CustomerProfile.objects.filter(user=customer).first()
            if prof:
                return prof.trust_score
        return 100

    def get_customer_flag_reasons(self, obj):
        customer = self._resolve_customer(obj)
        if customer:
            from accounts.models import CustomerFlag
            return list(CustomerFlag.objects.filter(customer=customer).order_by("-created_at").values_list("reason", flat=True)[:5])
        return []


# ==========================================
# WALK-IN CART ITEM SERIALIZER
# ==========================================

class WalkInCartItemSerializer(serializers.ModelSerializer):

    menu_name = serializers.CharField(
        source="menu_item.name",
        read_only=True
    )

    image = serializers.ImageField(
        source="menu_item.image",
        read_only=True
    )

    class Meta:

        model = WalkInCartItem

        fields = [

            "id",

            "menu_item",

            "menu_name",

            "image",

            "item_name",

            "item_price",

            "quantity",

            "total_price",

            "created_at"

        ]


# ==========================================
# WALK-IN CART SERIALIZER
# ==========================================

class WalkInCartSerializer(serializers.ModelSerializer):

    items = WalkInCartItemSerializer(
        many=True,
        read_only=True
    )

    total_items = serializers.SerializerMethodField()

    # ✅ Add shop_id and shop_name
    shop_id = serializers.IntegerField(
        source='shop.id',
        read_only=True
    )

    shop_name = serializers.CharField(
        source='shop.name',
        read_only=True
    )

    class Meta:

        model = WalkInCart

        fields = [

            "id",

            "cart_number",

            "customer",

            "customer_name",

            "customer_phone",

            "payment_method",

            "payment_status",

            "notes",

            "status",

            "total_amount",

            "total_items",

            "created_at",

            "updated_at",

            "items",

            "shop_id",      # ✅ added

            "shop_name",    # ✅ added

        ]

    def get_total_items(self, obj):

        total = 0

        for item in obj.items.all():

            total += item.quantity

        return total