from rest_framework import serializers

from .models import (
    Order,
    OrderItem
)


class OrderItemSerializer(
    serializers.ModelSerializer
):

    class Meta:

        model = OrderItem

        fields = "__all__"


class OrderSerializer(
    serializers.ModelSerializer
):

    items = (
        OrderItemSerializer(
            many=True,
            read_only=True
        )
    )

    customer_name = (
        serializers.SerializerMethodField()
    )

    customer_phone = (
        serializers.SerializerMethodField()
    )

    class Meta:

        model = Order

        fields = "__all__"

    def get_customer_name(
        self,
        obj
    ):

        if obj.customer_name:
            return obj.customer_name

        if obj.customer:

            return (
                obj.customer.get_full_name()
                or
                obj.customer.username
            )

        return None

    def get_customer_phone(
        self,
        obj
    ):

        if obj.customer_phone:
            return obj.customer_phone

        if (
            obj.customer
            and
            hasattr(
                obj.customer,
                "phone"
            )
        ):
            return obj.customer.phone

        return None