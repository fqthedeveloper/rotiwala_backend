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

    class Meta:

        model = WalkInCart

        fields = [

            "id",

            "cart_number",

            "customer",

            "customer_name",

            "customer_phone",

            "payment_method",

            "notes",

            "status",

            "total_amount",

            "total_items",

            "created_at",

            "updated_at",

            "items",

        ]

    def get_total_items(self, obj):

        total = 0

        for item in obj.items.all():

            total += item.quantity

        return total