from rest_framework import serializers

from .models import Cart
from .models import CartItem


class CartItemSerializer(serializers.ModelSerializer):

    item_name = serializers.CharField(
        source="menu_item.name",
        read_only=True
    )

    item_price = serializers.DecimalField(
        source="menu_item.price",
        max_digits=10,
        decimal_places=2,
        read_only=True
    )

    total_price = serializers.ReadOnlyField()

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


class CartSerializer(serializers.ModelSerializer):

    items = CartItemSerializer(
        many=True,
        read_only=True
    )

    class Meta:
        model = Cart

        fields = [
            "id",
            "customer",
            "items"
        ]