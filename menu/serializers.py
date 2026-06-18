from rest_framework import serializers

from .models import MenuCategory
from .models import MenuItem


class MenuItemSerializer(serializers.ModelSerializer):

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = MenuItem
        fields = "__all__"

    def get_image_url(self, obj):

        request = self.context.get("request")

        if obj.image:
            return request.build_absolute_uri(
                obj.image.url
            )

        return None
    

class MenuCategorySerializer(serializers.ModelSerializer):

    items = MenuItemSerializer(
        many=True,
        read_only=True
    )

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = MenuCategory
        fields = "__all__"

    def get_image_url(self, obj):

        request = self.context.get("request")

        if obj.image:
            return request.build_absolute_uri(
                obj.image.url
            )

        return None