import uuid
from datetime import timedelta
from django.utils import timezone
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal


from accounts.models import (
    User,
    CustomerProfile
)

from cart.models import (
    Cart,
    CartItem
)

from shops.models import Shop

from .models import (
    Order,
    OrderItem,
    WalkInCart,
    WalkInCartItem,
)

from .serializers import (
    OrderSerializer,
    WalkInCartSerializer
)

from notifications.fcm import (
    send_push_notification
)

from .websocket import (
    send_order_update
)

from .utils import (
    generate_order_number,
    generate_walkin_cart_number
)

from menu.models import (
    MenuItem
)




class PlaceOrderView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        shop_id = request.data.get("shop_id")

        if not shop_id:
            return Response(
                {
                    "error": "Shop ID required"
                },
                status=400
            )

        try:
            shop = Shop.objects.get(
                id=shop_id,
                is_active=True
            )

        except Shop.DoesNotExist:
            return Response(
                {
                    "error": "Shop not found"
                },
                status=404
            )

        try:
            cart = Cart.objects.get(
                customer=request.user
            )

        except Cart.DoesNotExist:
            return Response(
                {
                    "error": "Cart not found"
                },
                status=400
            )

        cart_items = CartItem.objects.filter(
            cart=cart
        )

        if not cart_items.exists():
            return Response(
                {
                    "error": "Cart Empty"
                },
                status=400
            )

        payment_method = request.data.get(
            "payment_method",
            "cash"
        )

        notes = request.data.get(
            "notes",
            ""
        )

        pickup_by_other_person = request.data.get(
            "pickup_by_other_person",
            False
        )

        pickup_person_name = request.data.get(
            "pickup_person_name",
            ""
        )

        pickup_person_phone = request.data.get(
            "pickup_person_phone",
            ""
        )

        # Validate only when another person collects

        if pickup_by_other_person:

            if not pickup_person_name:

                return Response(
                    {
                        "error":
                        "Pickup person name is required"
                    },
                    status=400
                ),

            if not pickup_person_phone:

                return Response(
                    {
                        "error":
                        "Pickup person phone is required"
                    },
                    status=400
                ),
                
        active_orders = Order.objects.filter(
            shop=shop,
            status__in=[
                "accepted",
                "preparing"
            ]
        ).count()

        estimated_minutes = 10

        if active_orders >= 5:
            estimated_minutes = 15

        if active_orders >= 10:
            estimated_minutes = 20

        if active_orders >= 15:
            estimated_minutes = 30

        estimated_ready_time = (
            timezone.now() +
            timedelta(
                minutes=estimated_minutes
            )
        )

        order = Order.objects.create(

            order_number=
            generate_order_number(),

            customer=request.user,

            shop=shop,

            customer_name=(
                request.user.get_full_name()
                or request.user.username
                or request.user.phone
            ),

            customer_phone=
            request.user.phone,

            payment_method=
            payment_method,

            payment_status=
            "pending",

            order_type=
            "online",

            notes=notes,

            status="pending",

            estimated_minutes=
            estimated_minutes,

            estimated_ready_time=
            estimated_ready_time,

            pickup_by_other_person=
            pickup_by_other_person,

            pickup_person_name=
            pickup_person_name,

            pickup_person_phone=
            pickup_person_phone,
        )

        total_amount = 0

        for item in cart_items:

            line_total = (
                item.menu_item.base_price *
                item.quantity
            )

            OrderItem.objects.create(

                order=order,

                item_name=item.menu_item.name,

                item_price=item.menu_item.base_price,

                quantity=item.quantity,

                total_price=line_total
            )

            total_amount += line_total

        order.total_amount = total_amount

        order.save()

        profile, created = (
            CustomerProfile.objects
            .get_or_create(
                user=request.user
            )
        )

        profile.total_orders += 1

        profile.save()

        manager = User.objects.filter(

            role="manager",

            manager_profile__shop=shop

        ).first()

        if manager and manager.fcm_token:

            send_push_notification(

                token=manager.fcm_token,

                title="🔥 New Order Received",

                body=(
                    f"Order #{order.order_number} "
                    f"₹{order.total_amount}"
                ),

                data={
                    "type": "new_order",
                    "order_id": str(order.id),
                    "shop_id": str(shop.id),
                }
            )

        cart_items.delete()

        return Response({

            "success": True,

            "message": "Order Placed Successfully",

            "order_id": order.id,

            "order_number": order.order_number,

            "total_amount": order.total_amount,

            "estimated_minutes": estimated_minutes,

            "estimated_ready_time": estimated_ready_time,

            "queue_count": active_orders

        })        
    


class ManagerOrdersView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        if request.user.role != "manager":
            return Response(
                {"error": "Permission denied"},
                status=403
            )

        manager_shop = (
            request.user
            .manager_profile
            .shop
        )

        selected_date = request.GET.get(
            "date"
        )

        orders = Order.objects.filter(
            shop=manager_shop
        )

        if selected_date:

            orders = orders.filter(
                ordered_at__date=selected_date
            )

        else:

            today = timezone.localdate()

            orders = orders.filter(
                ordered_at__date=today
            )

        orders = orders.order_by(
            "-ordered_at"
        )

        serializer = OrderSerializer(
            orders,
            many=True
        )

        return Response(
            serializer.data
        )


class AcceptOrderView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        order = Order.objects.get(id=pk)

        order.status = "accepted"
        order.accepted_at = timezone.now()
        order.save()
        send_order_update(order)

        if (
            order.customer and
            order.customer.fcm_token
        ):

            send_push_notification(
                token=order.customer.fcm_token,
                title="Order Accepted",
                body=f"Order #{order.order_number} accepted",
                data={
                    "type": "order",
                    "status": "accepted",
                    "order_id": str(order.id)
                }
            )

        return Response(
            {
                "message": "Order Accepted"
            }
        )


class RejectOrderView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        reason = request.data.get(
            "reason",
            "Order rejected"
        )

        order = Order.objects.get(id=pk)

        order.status = "rejected"
        order.rejection_reason = reason
        order.save()
        send_order_update(order)

        if order.customer:

            profile = CustomerProfile.objects.get(
                user=order.customer
            )

            profile.total_rejected_orders += 1
            profile.trust_score -= 3

            if profile.trust_score < 50:
                profile.is_flagged = True

            profile.save()

        if (
            order.customer and
            order.customer.fcm_token
        ):

            send_push_notification(
                token=order.customer.fcm_token,
                title="Order Rejected",
                body=reason,
                data={
                    "type": "order",
                    "status": "rejected",
                    "order_id": str(order.id)
                }
            )

        return Response(
            {
                "message": "Order Rejected"
            }
        )


class PreparingOrderView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        order = Order.objects.get(id=pk)

        order.status = "preparing"
        order.save()
        send_order_update(order)

        return Response(
            {
                "message": "Preparing"
            }
        )


class ReadyOrderView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        order = Order.objects.get(id=pk)

        order.status = "ready"
        order.ready_at = timezone.now()
        order.save()
        send_order_update(order)
        if (
            order.customer and
            order.customer.fcm_token
        ):

            send_push_notification(
                token=order.customer.fcm_token,
                title="Order Ready",
                body="Your order is ready for pickup",
                data={
                    "type": "order",
                    "status": "ready",
                    "order_id": str(order.id)
                }
            )

        return Response(
            {
                "message": "Order Ready"
            }
        )


class CollectedOrderView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        order = Order.objects.get(id=pk)

        if order.payment_status != "paid":

            return Response(
                {
                    "error": "Payment not received"
                },
                status=400
            )

        order.status = "collected"
        order.collected_at = timezone.now()
        order.save()
        send_order_update(order)

        if order.customer:

            profile = CustomerProfile.objects.get(
                user=order.customer
            )

            profile.total_completed_orders += 1
            profile.trust_score += 1
            profile.save()

        if (
            order.customer and
            order.customer.fcm_token
        ):

            send_push_notification(
                token=order.customer.fcm_token,
                title="Order Collected",
                body="Thank you for your order",
                data={
                    "type": "order",
                    "status": "collected",
                    "order_id": str(order.id)
                }
            )

        return Response(
            {
                "message": "Collected"
            }
        )


class CancelOrderView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        order = Order.objects.get(
            id=pk,
            customer=request.user
        )

        if order.status not in [
            "pending",
            "accepted"
        ]:

            return Response(
                {
                    "error": "Cannot cancel"
                },
                status=400
            )

        order.status = "cancelled"
        order.save()

        send_order_update(order)

        profile = CustomerProfile.objects.get(
            user=request.user
        )

        profile.total_cancelled_orders += 1
        profile.trust_score -= 10

        if profile.trust_score < 50:
            profile.is_flagged = True

        profile.save()

        return Response(
            {
                "message": "Order Cancelled"
            }
        )

class PaymentReceivedView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        order = Order.objects.get(
            id=pk
        )

        order.payment_status = "paid"

        order.save()
        send_order_update(order)

        return Response(
            {
                "message": "Payment Received"
            }
        )



class MyOrdersView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        orders = Order.objects.filter(
            customer=request.user
        ).order_by("-id")

        serializer = OrderSerializer(
            orders,
            many=True
        )

        return Response(serializer.data)

        
class OrderDetailView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):

        try:

            order = Order.objects.get(
                id=pk,
                customer=request.user
            )

        except Order.DoesNotExist:

            return Response(
                {
                    "error": "Order not found"
                },
                status=404
            )

        serializer = OrderSerializer(order)

        return Response(
            serializer.data
        )
        

class ManagerDashboardView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        shop = request.user.manager_profile.shop

        return Response({

            "pending": Order.objects.filter(
                shop=shop,
                status="pending"
            ).count(),

            "accepted": Order.objects.filter(
                shop=shop,
                status="accepted"
            ).count(),

            "preparing": Order.objects.filter(
                shop=shop,
                status="preparing"
            ).count(),

            "ready": Order.objects.filter(
                shop=shop,
                status="ready"
            ).count(),

            "collected": Order.objects.filter(
                shop=shop,
                status="collected"
            ).count(),

            "today_sales": Order.objects.filter(
                shop=shop,
                payment_status="paid"
            ).count()

        })


# ==========================================
# CUSTOMER SEARCH
# ==========================================

class CustomerSearchView(APIView):

    permission_classes = [IsAuthenticated]

    def normalize_phone(self, phone):

        if not phone:
            return ""

        phone = (
            phone.strip()
                 .replace(" ", "")
                 .replace("-", "")
        )

        if phone.startswith("+91"):
            phone = phone[3:]

        elif phone.startswith("91"):
            phone = phone[2:]

        return phone

    def get(self, request):

        phone = request.GET.get("phone", "")

        phone = self.normalize_phone(phone)

        if not phone:

            return Response({
                "found": False
            })

        possible_numbers = [

            phone,

            "+91" + phone,

            "91" + phone,

        ]

        customer = (
            User.objects
            .filter(
                role="customer",
                phone__in=possible_numbers
            )
            .first()
        )

        if not customer:

            return Response({

                "found": False,

                "phone": "+91" + phone,

            })

        profile, _ = CustomerProfile.objects.get_or_create(

            user=customer,

            defaults={

                "trust_score": 100,

                "total_orders": 0,

            }

        )

        return Response({

            "found": True,

            "id": customer.id,

            "name": customer.first_name or customer.username,

            "phone": customer.phone,

            "trust_score": profile.trust_score,

            "total_orders": profile.total_orders,

        })
        
        
# ==========================================
# GET OR CREATE CUSTOMER
# ==========================================

from django.db import transaction
from accounts.models import User, CustomerProfile


def get_or_create_customer(phone, name):

    if not phone:
        return None

    # ---------------------------------------
    # Normalize Phone
    # ---------------------------------------

    phone = (
        phone.strip()
        .replace(" ", "")
        .replace("-", "")
    )

    if phone.startswith("+91"):
        clean_phone = phone[3:]

    elif phone.startswith("91"):
        clean_phone = phone[2:]

    else:
        clean_phone = phone

    full_phone = "+91" + clean_phone

    possible_numbers = [

        clean_phone,

        "91" + clean_phone,

        full_phone,

    ]

    # ---------------------------------------
    # Existing Customer
    # ---------------------------------------

    customer = (

        User.objects

        .filter(

            role="customer",

            phone__in=possible_numbers,

        )

        .first()

    )

    if customer:

        CustomerProfile.objects.get_or_create(

            user=customer,

            defaults={

                "trust_score": 100,

                "total_orders": 0,

            }

        )

        return customer

    # ---------------------------------------
    # Create Customer
    # ---------------------------------------

    with transaction.atomic():

        customer = (

            User.objects

            .select_for_update()

            .filter(

                role="customer",

                phone__in=possible_numbers,

            )

            .first()

        )

        if customer:

            CustomerProfile.objects.get_or_create(

                user=customer,

                defaults={

                    "trust_score": 100,

                    "total_orders": 0,

                }

            )

            return customer

        username = clean_phone

        counter = 1

        while User.objects.filter(username=username).exists():

            username = f"{clean_phone}_{counter}"

            counter += 1

        customer = User(

            username=username,

            first_name=name or "Walk-In Customer",

            phone=full_phone,

            role="customer",

            is_active=True,

            is_phone_verified=True,

        )

        # ---------------------------------------
        # Default Password = Mobile Number
        # Example:
        # Phone : 9876543210
        # Password : 9876543210
        # ---------------------------------------

        customer.set_password(clean_phone)

        customer.save()

        CustomerProfile.objects.create(

            user=customer,

            trust_score=100,

            total_orders=0,

        )

        return customer
    

# ==========================================
# CREATE WALK-IN CART
# ==========================================

class CreateWalkInCartView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=status.HTTP_403_FORBIDDEN
            )

        try:

            shop = request.user.manager_profile.shop

        except Exception:

            return Response(
                {
                    "error": "Manager shop not assigned"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        customer_name = (
            request.data.get(
                "customer_name",
                ""
            )
            .strip()
        )

        customer_phone = (
            request.data.get(
                "customer_phone",
                ""
            )
            .strip()
        )

        payment_method = request.data.get(
            "payment_method",
            "cash"
        )

        notes = request.data.get(
            "notes",
            ""
        )

        # ------------------------------------
        # Normalize Phone
        # ------------------------------------

        if customer_phone:

            customer_phone = (
                customer_phone
                .replace(" ", "")
                .replace("-", "")
            )

            if customer_phone.startswith("+91"):

                pass

            elif customer_phone.startswith("91"):

                customer_phone = "+" + customer_phone

            else:

                customer_phone = "+91" + customer_phone

        # ------------------------------------
        # DO NOT CREATE CUSTOMER HERE
        # Customer will be created only
        # when the order is placed.
        # ------------------------------------

        cart = WalkInCart.objects.create(

            cart_number=generate_walkin_cart_number(),

            manager=request.user,

            shop=shop,

            customer=None,

            customer_name=customer_name,

            customer_phone=customer_phone,

            payment_method=payment_method,

            notes=notes,

            status="draft",

            total_amount=Decimal("0.00")

        )

        serializer = WalkInCartSerializer(cart)

        return Response(

            serializer.data,

            status=status.HTTP_201_CREATED

        )
        
class WalkInCartListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        shop = request.user.manager_profile.shop

        carts = WalkInCart.objects.filter(

            shop=shop,

            status="draft"

        ).order_by(

            "-updated_at"

        )

        serializer = WalkInCartSerializer(

            carts,

            many=True

        )

        return Response(

            serializer.data

        )
        
def update_walkin_cart_total(cart):

    total = Decimal("0.00")

    for item in cart.items.all():

        total += item.total_price

    cart.total_amount = total

    cart.save(update_fields=["total_amount", "updated_at"])
    

        
class WalkInCartDetailView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        try:

            cart = WalkInCart.objects.get(

                id=pk,

                manager=request.user

            )

        except WalkInCart.DoesNotExist:

            return Response(

                {
                    "error": "Cart not found"
                },

                status=404

            )

        serializer = WalkInCartSerializer(

            cart

        )

        return Response(

            serializer.data

        )


class AddWalkInCartItemView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        try:

            cart = WalkInCart.objects.get(

                id=pk,

                manager=request.user,

                status="draft"

            )

        except WalkInCart.DoesNotExist:

            return Response(
                {
                    "error": "Cart not found"
                },
                status=404
            )

        menu_item_id = request.data.get("menu_item")

        quantity = int(
            request.data.get(
                "quantity",
                1
            )
        )

        try:

            menu_item = MenuItem.objects.get(
                id=menu_item_id,
                is_available=True
            )

        except MenuItem.DoesNotExist:

            return Response(
                {
                    "error": "Menu item not found"
                },
                status=404
            )

        cart_item = WalkInCartItem.objects.filter(

            cart=cart,

            menu_item=menu_item

        ).first()

        if cart_item:

            cart_item.quantity += quantity

            cart_item.save()

        else:

            cart_item = WalkInCartItem.objects.create(

                cart=cart,

                menu_item=menu_item,

                item_name=menu_item.name,

                item_price=menu_item.base_price,

                quantity=quantity

            )

        update_walkin_cart_total(cart)

        serializer = WalkInCartSerializer(cart)

        return Response(serializer.data)
    
    
class UpdateWalkInCartItemView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        try:

            item = WalkInCartItem.objects.get(
                id=pk,
                cart__manager=request.user,
                cart__status="draft"
            )

        except WalkInCartItem.DoesNotExist:

            return Response(
                {
                    "error": "Item not found"
                },
                status=404
            )

        quantity = int(
            request.data.get(
                "quantity",
                1
            )
        )

        if quantity <= 0:

            item.delete()

            return Response(
                {
                    "message": "Item removed"
                }
            )

        item.quantity = quantity

        item.save()

        update_walkin_cart_total(item.cart)

        serializer = WalkInCartSerializer(item.cart)

        return Response(serializer.data)
    
    
class DeleteWalkInCartItemView(APIView):

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        try:

            item = WalkInCartItem.objects.get(
                id=pk,
                cart__manager=request.user,
                cart__status="draft"
            )

        except WalkInCartItem.DoesNotExist:

            return Response(
                {
                    "error": "Item not found"
                },
                status=404
            )

        cart = item.cart

        item.delete()

        update_walkin_cart_total(cart)

        serializer = WalkInCartSerializer(cart)

        return Response(serializer.data)
    

# ==========================================
# UPDATE WALK-IN CART
# ==========================================

class UpdateWalkInCartView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=status.HTTP_403_FORBIDDEN
            )

        try:

            cart = WalkInCart.objects.get(

                id=pk,

                manager=request.user,

                status="draft"

            )

        except WalkInCart.DoesNotExist:

            return Response(

                {
                    "error": "Cart not found"
                },

                status=status.HTTP_404_NOT_FOUND

            )

        # -------------------------------------
        # Customer Name
        # -------------------------------------

        customer_name = request.data.get(

            "customer_name",

            cart.customer_name

        ).strip()

        # -------------------------------------
        # Customer Phone
        # -------------------------------------

        customer_phone = request.data.get(

            "customer_phone",

            cart.customer_phone

        ).strip()

        if customer_phone:

            customer_phone = (

                customer_phone

                .replace(" ", "")

                .replace("-", "")

            )

            if customer_phone.startswith("+91"):

                pass

            elif customer_phone.startswith("91"):

                customer_phone = "+" + customer_phone

            else:

                customer_phone = "+91" + customer_phone

        # -------------------------------------
        # Payment Method
        # -------------------------------------

        payment_method = request.data.get(

            "payment_method",

            cart.payment_method

        )

        # -------------------------------------
        # Notes
        # -------------------------------------

        notes = request.data.get(

            "notes",

            cart.notes

        )

        # -------------------------------------
        # Search Existing Customer Only
        # DO NOT CREATE CUSTOMER
        # -------------------------------------

        customer = None

        if customer_phone:

            customer = User.objects.filter(

                role="customer",

                phone__in=[

                    customer_phone,

                    customer_phone.replace("+91", ""),

                    customer_phone.replace("+91", "91"),

                ]

            ).first()

        # -------------------------------------
        # Update Draft
        # -------------------------------------

        cart.customer = customer

        cart.customer_name = customer_name

        cart.customer_phone = customer_phone

        cart.payment_method = payment_method

        cart.notes = notes

        cart.save(

            update_fields=[

                "customer",

                "customer_name",

                "customer_phone",

                "payment_method",

                "notes",

                "updated_at",

            ]

        )

        serializer = WalkInCartSerializer(cart)

        return Response(

            serializer.data,

            status=status.HTTP_200_OK

        )
      
      
class PlaceWalkInCartView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        try:

            cart = WalkInCart.objects.get(

                id=pk,

                manager=request.user,

                status="draft"

            )

        except WalkInCart.DoesNotExist:

            return Response(
                {
                    "error": "Draft cart not found"
                },
                status=404
            )

        if not cart.items.exists():

            return Response(
                {
                    "error": "Cart is empty"
                },
                status=400
            )

        order = Order.objects.create(

            order_number=
            generate_walkin_cart_number(),

            customer=
            cart.customer,

            shop=
            cart.shop,

            payment_method=
            cart.payment_method,

            payment_status=
            "paid",

            order_type=
            "walkin",

            status=
            "accepted",

            accepted_at=
            timezone.now(),

            customer_name=
            cart.customer_name,

            customer_phone=
            cart.customer_phone,

            notes=
            cart.notes,

            total_amount=
            cart.total_amount

        )

        for item in cart.items.all():

            OrderItem.objects.create(

                order=order,

                item_name=
                item.item_name,

                item_price=
                item.item_price,

                quantity=
                item.quantity,

                total_price=
                item.total_price

            )

        if order.customer:

            profile, created = CustomerProfile.objects.get_or_create(
                user=order.customer
            )

            profile.total_orders += 1

            profile.save()

        cart.status = "placed"

        cart.save()

        cart.items.all().delete()

        serializer = OrderSerializer(order)

        return Response({

            "success": True,

            "message": "Walk-In Order Created",

            "order": serializer.data

        })
        
def update_order_total(order):

    total = Decimal("0.00")

    for item in order.items.all():

        total += item.total_price

    order.total_amount = total

    order.save(
        update_fields=[
            "total_amount"
        ]
    )
    
    
class UpdatePlacedOrderView(APIView):

    permission_classes = [IsAuthenticated]

    EDITABLE_STATUS = [
        "pending",
        "accepted",
        "preparing",
        "ready",
    ]

    def patch(self, request, pk):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        try:

            shop = request.user.manager_profile.shop

        except:

            return Response(
                {
                    "error": "Manager shop not assigned"
                },
                status=400
            )

        try:

            order = Order.objects.get(

                id=pk,

                shop=shop,

                order_type="walkin"

            )

        except Order.DoesNotExist:

            return Response(
                {
                    "error": "Walk-In order not found"
                },
                status=404
            )

        if order.status not in self.EDITABLE_STATUS:

            return Response(
                {
                    "error": "This order can no longer be edited."
                },
                status=400
            )

        customer_name = request.data.get(
            "customer_name",
            order.customer_name
        )

        customer_phone = request.data.get(
            "customer_phone",
            order.customer_phone
        )

# ==========================================
# UPDATE PLACED WALK-IN ORDER
# ==========================================

class UpdatePlacedOrderView(APIView):

    permission_classes = [IsAuthenticated]

    EDITABLE_STATUS = [

        "pending",

        "accepted",

        "preparing",

        "ready",

    ]
    
    @transaction.atomic
    def patch(self, request, pk):

        if request.user.role != "manager":

            return Response(

                {
                    "error": "Permission denied"
                },

                status=status.HTTP_403_FORBIDDEN

            )

        try:

            shop = request.user.manager_profile.shop

        except Exception:

            return Response(

                {
                    "error": "Manager shop not assigned"
                },

                status=status.HTTP_400_BAD_REQUEST

            )

        try:

            order = Order.objects.select_for_update().get(

                id=pk,

                shop=shop,

                order_type="walkin",

            )

        except Order.DoesNotExist:

            return Response(

                {
                    "error": "Walk-In order not found"
                },

                status=status.HTTP_404_NOT_FOUND

            )

        if order.status not in self.EDITABLE_STATUS:

            return Response(

                {
                    "error": "This order can no longer be edited."
                },

                status=status.HTTP_400_BAD_REQUEST

            )
        
        customer_name = request.data.get(

            "customer_name",

            order.customer_name

        ).strip()

        customer_phone = request.data.get(

            "customer_phone",

            order.customer_phone

        ).strip()
        
        customer = None

        if customer_phone:

            customer_phone = (

                customer_phone

                .replace(" ", "")

                .replace("-", "")

            )

            if customer_phone.startswith("+91"):

                pass

            elif customer_phone.startswith("91"):

                customer_phone = "+" + customer_phone

            else:

                customer_phone = "+91" + customer_phone

            customer = get_or_create_customer(

                customer_phone,

                customer_name,

            )
            
        payment_method = request.data.get(

            "payment_method",

            order.payment_method

        )

        payment_status = request.data.get(

            "payment_status",

            order.payment_status

        )

        notes = request.data.get(

            "notes",

            order.notes

        )
        order.customer = customer

        order.customer_name = (

            customer.first_name

            if customer

            else customer_name

        )

        order.customer_phone = (

            customer.phone

            if customer

            else customer_phone

        )

        order.payment_method = payment_method

        order.payment_status = payment_status

        order.notes = notes
        
        estimated_minutes = request.data.get(

            "estimated_minutes"

        )

        if estimated_minutes is not None:

            try:

                estimated_minutes = int(

                    estimated_minutes

                )

                if estimated_minutes > 0:

                    order.estimated_minutes = (

                        estimated_minutes

                    )

                    order.estimated_ready_time = (

                        timezone.now()

                        +

                        timedelta(

                            minutes=estimated_minutes

                        )

                    )

            except ValueError:

                pass
            
            pickup_by_other_person = request.data.get(

                "pickup_by_other_person"

            )

            if pickup_by_other_person is not None:

                order.pickup_by_other_person = (

                    pickup_by_other_person

                )

            order.pickup_person_name = request.data.get(

                "pickup_person_name",

                order.pickup_person_name

            )

            order.pickup_person_phone = request.data.get(

                "pickup_person_phone",

                order.pickup_person_phone

            )
        order.save()
        if customer:

            CustomerProfile.objects.get_or_create(

                user=customer,

                defaults={

                    "trust_score": 100,

                    "total_orders": 0,

                }

            )
            send_order_update(

            order

        )
        
            serializer = OrderSerializer(

            order

        )
        return Response(

            {

                "success": True,

                "message": "Walk-In order updated successfully.",

                "order": serializer.data,

            },

            status=status.HTTP_200_OK

        )
                    

class AddPlacedOrderItemView(APIView):

    permission_classes = [IsAuthenticated]

    EDITABLE_STATUS = [
        "pending",
        "accepted",
        "preparing",
        "ready",
    ]

    def post(self, request, pk):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        try:

            shop = request.user.manager_profile.shop

        except Exception:

            return Response(
                {
                    "error": "Manager shop not assigned"
                },
                status=400
            )

        try:

            order = Order.objects.get(
                id=pk,
                shop=shop,
                order_type="walkin"
            )

        except Order.DoesNotExist:

            return Response(
                {
                    "error": "Walk-In order not found"
                },
                status=404
            )

        if order.status not in self.EDITABLE_STATUS:

            return Response(
                {
                    "error": "Order cannot be edited."
                },
                status=400
            )

        menu_item_id = request.data.get("menu_item")

        quantity = int(
            request.data.get(
                "quantity",
                1
            )
        )

        if quantity <= 0:

            quantity = 1

        if not menu_item_id:

            return Response(
                {
                    "error": "menu_item is required"
                },
                status=400
            )

        try:

            menu_item = MenuItem.objects.get(
                id=menu_item_id,
                is_available=True
            )

        except MenuItem.DoesNotExist:

            return Response(
                {
                    "error": "Menu item not found"
                },
                status=404
            )

        existing_item = OrderItem.objects.filter(

            order=order,

            item_name=menu_item.name,

            item_price=menu_item.base_price

        ).first()

        if existing_item:

            existing_item.quantity += quantity

            existing_item.total_price = (
                existing_item.item_price *
                existing_item.quantity
            )

            existing_item.save()

        else:

            OrderItem.objects.create(

                order=order,

                item_name=menu_item.name,

                item_price=menu_item.base_price,

                quantity=quantity,

                total_price=(
                    menu_item.base_price *
                    quantity
                )

            )

        update_order_total(order)

        send_order_update(order)

        serializer = OrderSerializer(order)

        return Response({

            "success": True,

            "message": "Item added successfully.",

            "order": serializer.data

        })
        

class UpdatePlacedOrderItemView(APIView):

    permission_classes = [IsAuthenticated]

    EDITABLE_STATUS = [
        "pending",
        "accepted",
        "preparing",
        "ready",
    ]

    def patch(self, request, pk):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        try:

            item = OrderItem.objects.select_related(
                "order"
            ).get(
                id=pk
            )

        except OrderItem.DoesNotExist:

            return Response(
                {
                    "error": "Order item not found"
                },
                status=404
            )

        order = item.order

        if order.order_type != "walkin":

            return Response(
                {
                    "error": "Only Walk-In orders can be edited."
                },
                status=400
            )

        try:

            shop = request.user.manager_profile.shop

        except:

            return Response(
                {
                    "error": "Manager shop not assigned"
                },
                status=400
            )

        if order.shop != shop:

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        if order.status not in self.EDITABLE_STATUS:

            return Response(
                {
                    "error": "Order cannot be edited."
                },
                status=400
            )

        quantity = request.data.get(
            "quantity"
        )

        if quantity is None:

            return Response(
                {
                    "error": "quantity is required"
                },
                status=400
            )

        try:

            quantity = int(quantity)

        except:

            return Response(
                {
                    "error": "Invalid quantity"
                },
                status=400
            )

        if quantity <= 0:

            item.delete()

            update_order_total(order)

            send_order_update(order)

            serializer = OrderSerializer(order)

            return Response({

                "success": True,

                "message": "Item removed.",

                "order": serializer.data

            })

        item.quantity = quantity

        item.total_price = (
            item.item_price *
            quantity
        )

        item.save()

        update_order_total(order)

        send_order_update(order)

        serializer = OrderSerializer(order)

        return Response({

            "success": True,

            "message": "Quantity updated.",

            "order": serializer.data

        })
        
class DeletePlacedOrderItemView(APIView):

    permission_classes = [IsAuthenticated]

    EDITABLE_STATUS = [
        "pending",
        "accepted",
        "preparing",
        "ready",
    ]

    def delete(self, request, pk):

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        try:

            item = OrderItem.objects.select_related(
                "order"
            ).get(
                id=pk
            )

        except OrderItem.DoesNotExist:

            return Response(
                {
                    "error": "Order item not found"
                },
                status=404
            )

        order = item.order

        if order.order_type != "walkin":

            return Response(
                {
                    "error": "Only Walk-In orders can be edited."
                },
                status=400
            )

        try:

            shop = request.user.manager_profile.shop

        except:

            return Response(
                {
                    "error": "Manager shop not assigned"
                },
                status=400
            )

        if order.shop != shop:

            return Response(
                {
                    "error": "Permission denied"
                },
                status=403
            )

        if order.status not in self.EDITABLE_STATUS:

            return Response(
                {
                    "error": "This order can no longer be edited."
                },
                status=400
            )

        if order.items.count() == 1:

            return Response(
                {
                    "error": "Order must contain at least one item."
                },
                status=400
            )

        item.delete()

        update_order_total(order)

        send_order_update(order)

        serializer = OrderSerializer(order)

        return Response({

            "success": True,

            "message": "Item deleted successfully.",

            "order": serializer.data

        })