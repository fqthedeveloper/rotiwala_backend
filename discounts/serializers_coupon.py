from django.utils import timezone

from rest_framework import serializers

from .coupon_models import (
    Coupon,
    CouponUsage,
)


class CouponSerializer(serializers.ModelSerializer):

    is_running = serializers.ReadOnlyField()

    class Meta:

        model = Coupon

        fields = "__all__"

        read_only_fields = (
            "used_count",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):

        instance = self.instance

        shop = attrs.get(
            "shop",
            getattr(instance, "shop", None)
        )

        code = attrs.get(
            "code",
            getattr(instance, "code", None)
        )

        value = attrs.get(
            "value",
            getattr(instance, "value", None)
        )

        discount_type = attrs.get(
            "discount_type",
            getattr(instance, "discount_type", None)
        )

        minimum_order_amount = attrs.get(
            "minimum_order_amount",
            getattr(
                instance,
                "minimum_order_amount",
                0
            )
        )

        maximum_discount_amount = attrs.get(
            "maximum_discount_amount",
            getattr(
                instance,
                "maximum_discount_amount",
                None
            )
        )

        start_date = attrs.get(
            "start_date",
            getattr(instance, "start_date", None)
        )

        end_date = attrs.get(
            "end_date",
            getattr(instance, "end_date", None)
        )

        usage_limit = attrs.get(
            "usage_limit",
            getattr(instance, "usage_limit", 0)
        )

        per_customer_limit = attrs.get(
            "per_customer_limit",
            getattr(
                instance,
                "per_customer_limit",
                1
            )
        )

        # --------------------------
        # Dates
        # --------------------------

        if start_date >= end_date:

            raise serializers.ValidationError(
                "End date must be after start date."
            )

        # --------------------------
        # Discount
        # --------------------------

        if discount_type == "percentage":

            if value <= 0:

                raise serializers.ValidationError(
                    "Percentage must be greater than 0."
                )

            if value > 100:

                raise serializers.ValidationError(
                    "Percentage cannot exceed 100."
                )

        if discount_type == "fixed":

            if value <= 0:

                raise serializers.ValidationError(
                    "Fixed discount must be greater than 0."
                )

        # --------------------------
        # Minimum Order
        # --------------------------

        if minimum_order_amount < 0:

            raise serializers.ValidationError(
                "Minimum order cannot be negative."
            )

        # --------------------------
        # Maximum Discount
        # --------------------------

        if (
            maximum_discount_amount
            and
            maximum_discount_amount <= 0
        ):

            raise serializers.ValidationError(
                "Maximum discount must be greater than zero."
            )

        # --------------------------
        # Usage Limit
        # --------------------------

        if usage_limit < 0:

            raise serializers.ValidationError(
                "Usage limit cannot be negative."
            )

        if per_customer_limit <= 0:

            raise serializers.ValidationError(
                "Per customer limit must be greater than zero."
            )

        # --------------------------
        # Duplicate Code
        # --------------------------

        qs = Coupon.objects.filter(
            code__iexact=code,
            shop=shop
        )

        if instance:

            qs = qs.exclude(
                pk=instance.pk
            )

        if qs.exists():

            raise serializers.ValidationError(
                "Coupon code already exists."
            )

        return attrs


class CouponUsageSerializer(
    serializers.ModelSerializer
):

    class Meta:

        model = CouponUsage

        fields = "__all__"
        


class UsageSummarySerializer(serializers.Serializer):
    """Serializer for aggregated usage data per date."""
    date = serializers.DateField()
    total_usage_count = serializers.IntegerField()
    total_discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_usage_count = serializers.IntegerField()
    coupon_usage_count = serializers.IntegerField()
    discount_total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    coupon_total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)


class UsageListSerializer(serializers.Serializer):
    """Serializer for individual usage records (unified)."""
    id = serializers.IntegerField()
    type = serializers.CharField()  # 'discount' or 'coupon'
    shop = serializers.IntegerField(source='shop.id')
    shop_name = serializers.CharField(source='shop.name')
    order = serializers.IntegerField(source='order.id')
    order_number = serializers.CharField(source='order.order_number')
    customer = serializers.IntegerField(source='customer.id')
    customer_name = serializers.CharField(source='customer.get_full_name')
    order_type = serializers.CharField()
    original_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    discount_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    final_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    created_at = serializers.DateTimeField()
    # For discount/coupon name
    discount_name = serializers.SerializerMethodField()

    def get_discount_name(self, obj):
        if hasattr(obj, 'discount'):
            return obj.discount.name
        elif hasattr(obj, 'coupon'):
            return obj.coupon.name
        return None