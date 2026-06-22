from rest_framework import serializers

from .models import Cart
from .models import CartItem


class CartItemSerializer(serializers.ModelSerializer):

    item_name = serializers.CharField(
        source="menu_item.name",
        read_only=True
    )

    item_price = serializers.DecimalField(
        source="menu_item.base_price",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    total_price = serializers.SerializerMethodField()

    class Meta:

        model = CartItem

        fields = [
            "id",
            "menu_item",
            "item_name",
            "item_price",
            "quantity",
            "total_price"
        ]

    def get_total_price(self, obj):

        return obj.menu_item.base_price * obj.quantity


class CartSerializer(serializers.ModelSerializer):

    items = CartItemSerializer(
        many=True,
        read_only=True
    )

    total_amount = serializers.SerializerMethodField()

    class Meta:

        model = Cart

        fields = [
            "id",
            "customer",
            "items",
            "total_amount"
        ]

    def get_total_amount(self, obj):

        total = 0

        for item in obj.items.all():

            total += item.menu_item.base_price * item.quantity

        return total