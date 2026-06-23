import uuid
from datetime import timedelta
from django.utils import timezone
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
    OrderItem
)

from .serializers import (
    OrderSerializer
)

from notifications.fcm import (
    send_push_notification
)

from .websocket import (
    send_order_update
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

        order_number=str(uuid.uuid4())[:10],

        customer=request.user,

        shop=shop,

        payment_method=payment_method,

        payment_status="pending",

        order_type="online",

        notes=notes,

        status="pending",

        estimated_minutes=estimated_minutes,

        estimated_ready_time=estimated_ready_time,

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


class WalkInOrderView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        order = Order.objects.create(

            order_number=str(uuid.uuid4())[:10],

            shop_id=request.data.get(
                "shop_id"
            ),

            order_type="walkin",

            customer_name=request.data.get(
                "customer_name"
            ),

            customer_phone=request.data.get(
                "customer_phone"
            ),

            payment_method=request.data.get(
                "payment_method",
                "cash"
            ),

            payment_status="paid",

            status="accepted",

            total_amount=request.data.get(
                "total_amount",
                0
            ),
        )

        return Response(
            {
                "message": "Walk-In Order Created",
                "order_id": order.id
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

        return Response(
            {
                "message": "Payment Received"
            }
        )
        
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