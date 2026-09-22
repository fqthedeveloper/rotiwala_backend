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
            if quantity < 1 or quantity > 99:
                return Response(
                    {"error": "Quantity must be between 1 and 99."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (TypeError, ValueError):
            return Response(
                {"error": "Invalid quantity provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

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

        if not menu_item.is_available or not getattr(menu_item, 'is_active', True):
            return Response(
                {
                    "error": f"Item '{menu_item.name}' is currently unavailable."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        cart, created = Cart.objects.get_or_create(
            customer=request.user
        )

        # Cross-shop protection: ensure all cart items belong to the same branch
        existing_first_item = cart.items.select_related('menu_item').first()
        if existing_first_item and existing_first_item.menu_item.shop_id != menu_item.shop_id:
            return Response(
                {
                    "error": "Your cart contains items from another branch. Please clear your cart before adding items from this branch."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            menu_item=menu_item
        )

        if created:
            cart_item.quantity = quantity
        else:
            new_qty = cart_item.quantity + quantity
            if new_qty > 99:
                return Response(
                    {"error": "Maximum quantity allowed per item is 99."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            cart_item.quantity = new_qty

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

        try:
            quantity = int(quantity)
        except (TypeError, ValueError):
            return Response(
                {"error": "Quantity must be an integer."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if quantity > 99:
            return Response(
                {"error": "Maximum quantity allowed per item is 99."},
                status=status.HTTP_400_BAD_REQUEST
            )

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