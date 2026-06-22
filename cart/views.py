from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Cart
from .models import CartItem

from menu.models import MenuItem

from .serializers import CartSerializer


class CartView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        cart, created = Cart.objects.get_or_create(
            customer=request.user
        )

        serializer = CartSerializer(cart)

        return Response(serializer.data)


class AddToCartView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        print("REQUEST DATA:", request.data)

        menu_item_id = request.data.get("menu_item")
        quantity = request.data.get("quantity", 1)

        if not menu_item_id:
            return Response(
                {
                    "error": "menu_item is required"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            quantity = int(quantity)
        except:
            quantity = 1

        try:

            menu_item = MenuItem.objects.get(
                id=menu_item_id
            )

        except MenuItem.DoesNotExist:

            return Response(
                {
                    "error": f"Menu item with id {menu_item_id} not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        cart, created = Cart.objects.get_or_create(
            customer=request.user
        )

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            menu_item=menu_item
        )

        if created:
            cart_item.quantity = quantity
        else:
            cart_item.quantity += quantity

        cart_item.save()

        return Response(
            {
                "success": True,
                "message": "Item added to cart",
                "cart_item_id": cart_item.id,
                "menu_item": menu_item.name,
                "quantity": cart_item.quantity
            }
        )


class UpdateCartItemView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):

        quantity = request.data.get("quantity")

        try:

            cart_item = CartItem.objects.get(
                id=pk,
                cart__customer=request.user
            )

        except CartItem.DoesNotExist:

            return Response(
                {
                    "error": "Cart item not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        quantity = int(quantity)

        if quantity <= 0:

            cart_item.delete()

            return Response(
                {
                    "message": "Item removed"
                }
            )

        cart_item.quantity = quantity
        cart_item.save()

        return Response(
            {
                "message": "Quantity updated"
            }
        )


class RemoveCartItemView(APIView):

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):

        deleted, _ = CartItem.objects.filter(
            id=pk,
            cart__customer=request.user
        ).delete()

        if deleted == 0:

            return Response(
                {
                    "error": "Item not found"
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            {
                "message": "Item removed successfully"
            }
        )


class ClearCartView(APIView):

    permission_classes = [IsAuthenticated]

    def delete(self, request):

        cart = Cart.objects.filter(
            customer=request.user
        ).first()

        if cart:
            cart.items.all().delete()

        return Response(
            {
                "message": "Cart cleared"
            }
        )
        


class CartCountView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def get(self, request):

        cart = Cart.objects.filter(
            customer=request.user
        ).first()

        if not cart:

            return Response({
                "count": 0
            })

        count = sum(
            item.quantity
            for item in cart.items.all()
        )

        return Response({
            "count": count
        })