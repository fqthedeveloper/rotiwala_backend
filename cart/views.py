from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Cart
from .models import CartItem

from menu.models import MenuItem

from .serializers import CartSerializer


class CartView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        cart, created = Cart.objects.get_or_create(
            customer=request.user
        )

        serializer = CartSerializer(cart)

        return Response(serializer.data)


class AddToCartView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def post(self, request):

        item_id = request.data.get("item_id")

        quantity = int(
            request.data.get("quantity", 1)
        )

        menu_item = MenuItem.objects.get(
            id=item_id
        )

        cart, created = Cart.objects.get_or_create(
            customer=request.user
        )

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            menu_item=menu_item
        )

        if not created:
            cart_item.quantity += quantity
        else:
            cart_item.quantity = quantity

        cart_item.save()

        return Response({
            "message": "Item added"
        })


class RemoveCartItemView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def delete(self, request, pk):

        CartItem.objects.filter(
            id=pk,
            cart__customer=request.user
        ).delete()

        return Response({
            "message": "Deleted"
        })