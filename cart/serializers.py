from rest_framework import serializers

from .models import Cart
from .models import CartItem


class CartItemSerializer(serializers.ModelSerializer):
    item_name = serializers.SerializerMethodField()
    item_price = serializers.SerializerMethodField()
    variant = serializers.IntegerField(source="variant.id", read_only=True)
    variant_name = serializers.CharField(source="variant.name", read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "menu_item",
            "item_name",
            "item_price",
            "variant",
            "variant_name",
            "quantity",
            "total_price",
        ]

    def get_item_name(self, obj):
        if obj.variant:
            return f"{obj.menu_item.name} ({obj.variant.name})"
        return obj.menu_item.name

    def get_item_price(self, obj):
        return obj.unit_price

    def get_total_price(self, obj):
        return obj.total_price


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
            total += item.total_price
        return total