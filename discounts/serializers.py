from django.utils import timezone

from rest_framework import serializers

from .models import Discount


class DiscountSerializer(serializers.ModelSerializer):

    banner_url = serializers.SerializerMethodField()

    status = serializers.ReadOnlyField()

    discount_text = serializers.ReadOnlyField()

    notification_heading = serializers.ReadOnlyField()

    notification_message = serializers.ReadOnlyField()

    class Meta:

        model = Discount

        fields = "__all__"

        read_only_fields = (
            "created_at",
            "updated_at",
        )

    def get_banner_url(self, obj):

        request = self.context.get("request")

        if not obj.banner_image:
            return None

        if request:
            return request.build_absolute_uri(
                obj.banner_image.url
            )

        return obj.banner_image.url

    def validate(self, attrs):

        instance = self.instance

        shop = attrs.get(
            "shop",
            getattr(instance, "shop", None)
        )

        apply_on = attrs.get(
            "apply_on",
            getattr(instance, "apply_on", None)
        )

        category = attrs.get(
            "category",
            getattr(instance, "category", None)
        )

        menu_item = attrs.get(
            "menu_item",
            getattr(instance, "menu_item", None)
        )

        discount_type = attrs.get(
            "discount_type",
            getattr(instance, "discount_type", None)
        )

        value = attrs.get(
            "value",
            getattr(instance, "value", None)
        )

        start_date = attrs.get(
            "start_date",
            getattr(instance, "start_date", None)
        )

        end_date = attrs.get(
            "end_date",
            getattr(instance, "end_date", None)
        )

        if start_date >= end_date:

            raise serializers.ValidationError(
                "End date must be after start date."
            )

        if discount_type == "percentage":

            if value <= 0 or value > 100:

                raise serializers.ValidationError(
                    "Percentage discount must be between 1 and 100."
                )

        if discount_type == "fixed":

            if value <= 0:

                raise serializers.ValidationError(
                    "Fixed discount must be greater than zero."
                )

        if apply_on == "shop":

            attrs["category"] = None
            attrs["menu_item"] = None

        elif apply_on == "category":

            if category is None:

                raise serializers.ValidationError(
                    "Category is required."
                )

            if category.shop_id != shop.id:

                raise serializers.ValidationError(
                    "Category does not belong to selected shop."
                )

            attrs["menu_item"] = None

        elif apply_on == "item":

            if menu_item is None:

                raise serializers.ValidationError(
                    "Menu item is required."
                )

            if menu_item.shop_id != shop.id:

                raise serializers.ValidationError(
                    "Menu item does not belong to selected shop."
                )

            attrs["category"] = menu_item.category

        queryset = Discount.objects.filter(
            shop=shop,
            apply_on=apply_on,
            is_active=True,
        )

        if instance:

            queryset = queryset.exclude(
                pk=instance.pk
            )

        if apply_on == "shop":

            if queryset.exists():

                raise serializers.ValidationError(
                    "Another active shop discount already exists."
                )

        elif apply_on == "category":

            if queryset.filter(
                category=category
            ).exists():

                raise serializers.ValidationError(
                    "Another active category discount already exists."
                )

        elif apply_on == "item":

            if queryset.filter(
                menu_item=menu_item
            ).exists():

                raise serializers.ValidationError(
                    "Another active item discount already exists."
                )

        return attrs