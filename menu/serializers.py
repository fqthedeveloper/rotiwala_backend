# menu/serializers.py

import json
from rest_framework import serializers
from .models import MenuCategory, MenuItem, MenuItemVariant
from discounts.services import get_discounted_price


class MenuItemVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemVariant
        fields = ["id", "name", "price", "is_active", "is_available"]


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
    variants = MenuItemVariantSerializer(many=True, read_only=True)
    has_variants = serializers.SerializerMethodField()
    min_price = serializers.SerializerMethodField()
    max_price = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(default=True, required=False)
    is_available = serializers.BooleanField(default=True, required=False)

    class Meta:
        model = MenuItem
        fields = [
            "id", "shop", "category", "name", "description",
            "category_name", "image", "image_url", "base_price",
            "original_price", "discount_amount", "final_price",
            "has_discount", "discount_percentage", "discount_name",
            "variants", "has_variants", "min_price", "max_price",
            "is_active", "is_available", "created_at",
        ]

    def get_image_url(self, obj):
        if not obj.image:
            return None
        url = obj.image.url
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(url)
        return url

    def get_has_variants(self, obj):
        return obj.variants.filter(is_active=True).exists()

    def get_min_price(self, obj):
        active_vars = obj.variants.filter(is_active=True)
        if active_vars.exists():
            return min(v.price for v in active_vars)
        return obj.base_price

    def get_max_price(self, obj):
        active_vars = obj.variants.filter(is_active=True)
        if active_vars.exists():
            return max(v.price for v in active_vars)
        return obj.base_price

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if ret.get("image_url"):
            ret["image"] = ret["image_url"]
        active_vars = instance.variants.filter(is_active=True)
        ret["variants"] = MenuItemVariantSerializer(active_vars, many=True).data
        ret["has_variants"] = len(ret["variants"]) > 0
        if ret["has_variants"]:
            prices = [float(v["price"]) for v in ret["variants"]]
            ret["min_price"] = min(prices)
            ret["max_price"] = max(prices)
        else:
            ret["min_price"] = float(instance.base_price)
            ret["max_price"] = float(instance.base_price)
        return ret

    def _handle_variants(self, instance, variants_data):
        if variants_data is None:
            return
        if isinstance(variants_data, str):
            try:
                variants_data = json.loads(variants_data)
            except Exception:
                variants_data = []

        if not isinstance(variants_data, list):
            return

        kept_ids = []
        for v in variants_data:
            v_id = v.get("id")
            name = (v.get("name") or "").strip()
            price = v.get("price")
            if not name or price is None:
                continue
            is_avail = v.get("is_available", True)
            is_active = v.get("is_active", True)
            if v_id:
                try:
                    variant_obj = MenuItemVariant.objects.get(id=v_id, menu_item=instance)
                    variant_obj.name = name
                    variant_obj.price = price
                    variant_obj.is_available = is_avail
                    variant_obj.is_active = is_active
                    variant_obj.save()
                    kept_ids.append(variant_obj.id)
                except MenuItemVariant.DoesNotExist:
                    new_var = MenuItemVariant.objects.create(
                        menu_item=instance,
                        name=name,
                        price=price,
                        is_available=is_avail,
                        is_active=is_active
                    )
                    kept_ids.append(new_var.id)
            else:
                new_var = MenuItemVariant.objects.create(
                    menu_item=instance,
                    name=name,
                    price=price,
                    is_available=is_avail,
                    is_active=is_active
                )
                kept_ids.append(new_var.id)

        # Remove variants that were deleted
        instance.variants.exclude(id__in=kept_ids).delete()

    def create(self, validated_data):
        if "is_active" not in validated_data:
            validated_data["is_active"] = True
        request = self.context.get("request")
        variants_data = request.data.get("variants") if request else None
        item = super().create(validated_data)
        if variants_data:
            self._handle_variants(item, variants_data)
        return item

    def update(self, instance, validated_data):
        request = self.context.get("request")
        if request and "is_active" not in request.data:
            validated_data.pop("is_active", None)
        variants_data = request.data.get("variants") if request else None
        item = super().update(instance, validated_data)
        if variants_data is not None:
            self._handle_variants(item, variants_data)
        return item

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