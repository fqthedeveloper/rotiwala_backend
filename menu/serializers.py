# menu/serializers.py

from rest_framework import serializers
from .models import MenuCategory, MenuItem
from discounts.services import get_discounted_price

class MenuItemSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()
    shop = serializers.ReadOnlyField(source="shop.id")
    category_name = serializers.ReadOnlyField(source="category.name")
    original_price = serializers.SerializerMethodField()
    discount_amount = serializers.SerializerMethodField()
    final_price = serializers.SerializerMethodField()
    has_discount = serializers.SerializerMethodField()
    discount_percentage = serializers.SerializerMethodField()
    discount_name = serializers.SerializerMethodField()

    class Meta:
        model = MenuItem
        fields = [
            "id", "shop", "category", "name", "description",
            "category_name", "image", "image_url", "base_price",
            "original_price", "discount_amount", "final_price",
            "has_discount", "discount_percentage", "discount_name",
            "is_active", "is_available", "created_at",
        ]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        url = obj.image.url
        request = self.context.get("request")
        if request:
            full_url = request.build_absolute_uri(url)
        else:
            full_url = url

        if full_url.startswith("/"):
            full_url = f"https://backend.alidarbar.in{full_url}"

        if "127.0.0.1:8000" in full_url or "localhost:8000" in full_url or "testserver" in full_url:
            full_url = full_url.replace("http://127.0.0.1:8000", "https://backend.alidarbar.in")
            full_url = full_url.replace("http://localhost:8000", "https://backend.alidarbar.in")
            full_url = full_url.replace("http://testserver", "https://backend.alidarbar.in")

        if "backend.alidarbar.in" in full_url and full_url.startswith("http://"):
            full_url = full_url.replace("http://", "https://")

        return full_url

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if ret.get("image_url"):
            ret["image"] = ret["image_url"]
        return ret

    def _discount(self, obj):
        if not hasattr(obj, "_discount_cache"):
            obj._discount_cache = get_discounted_price(obj)
        return obj._discount_cache

    def get_original_price(self, obj):
        return self._discount(obj)["original_price"]
    def get_discount_amount(self, obj):
        return self._discount(obj)["discount_amount"]
    def get_final_price(self, obj):
        return self._discount(obj)["final_price"]
    def get_has_discount(self, obj):
        return self._discount(obj)["has_discount"]
    def get_discount_percentage(self, obj):
        return self._discount(obj)["discount_percentage"]
    def get_discount_name(self, obj):
        discount = self._discount(obj)["discount"]
        return discount.name if discount else None


class MenuCategorySerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)

    class Meta:
        model = MenuCategory
        fields = ["id", "name", "is_active", "created_at", "items"]