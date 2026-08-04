import uuid
from datetime import timedelta
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from decimal import Decimal
from django.db import IntegrityError
from django.utils.dateparse import parse_datetime
from whatsapp.services import WhatsAppService   


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
    generate_online_order_number,
    generate_walkin_cart_number,
    generate_walkin_order_number,    
)

from menu.models import (
    MenuItem
)

from .models import Order, OrderItem
from .serializers import OrderSerializer
from .utils import generate_online_order_number
from django.db import transaction
from discounts.offer_engine import OfferEngine                          # <-- import OfferEngine
from discounts.models import Discount, DiscountUsage                # <-- for usage tracking
from discounts.coupon_models import CouponUsage            # <-- for coupon usage


import math

def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in km between two coordinates."""
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c

# Add this function at the end of the file
def orders_root(request):
    """
    Root endpoint for orders API
    """
    return Response({
        'message': 'Orders API',
        'endpoints': {
            'place': '/api/orders/place/',
            'my_orders': '/api/orders/my-orders/',
            'manager': '/api/orders/manager/',
            'receipt': '/api/orders/receipt/<id>/',
        }
    })
    

# ==========================================
# PLACE ORDER VIEW (UPDATED)
# ==========================================

class PlaceOrderView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        # ============================================
        # 1. Validate basic inputs (unchanged)
        # ============================================
        shop_id = request.data.get("shop_id")
        if not shop_id:
            return Response({"error": "Shop ID required"}, status=400)

        try:
            shop = Shop.objects.get(id=shop_id, is_active=True)
        except Shop.DoesNotExist:
            return Response({"error": "Shop not found"}, status=404)

        try:
            cart = Cart.objects.get(customer=request.user)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found"}, status=400)

        cart_items = CartItem.objects.filter(cart=cart)
        if not cart_items.exists():
            return Response({"error": "Cart Empty"}, status=400)

        # -------------------------------------------
        # Delivery option and address
        # -------------------------------------------
        delivery_option = request.data.get("delivery_option", "pickup")
        delivery_address = request.data.get("delivery_address", "").strip()
        delivery_lat = request.data.get("delivery_latitude")
        delivery_lng = request.data.get("delivery_longitude")

        if delivery_option == "delivery":
            if not delivery_address:
                return Response({"error": "Delivery address is required"}, status=400)
            if delivery_lat is None or delivery_lng is None:
                return Response({"error": "Delivery latitude and longitude are required"}, status=400)
            if shop.latitude is None or shop.longitude is None:
                return Response({"error": "Shop location is not set, cannot deliver"}, status=400)
            distance = haversine(
                float(shop.latitude), float(shop.longitude),
                float(delivery_lat), float(delivery_lng)
            )
            if distance > 2.0:
                return Response({
                    "error": f"Shop is {distance:.2f} km away. We only deliver within 2 km."
                }, status=400)

        # -------------------------------------------
        # Payment & pickup
        # -------------------------------------------
        payment_method = request.data.get("payment_method", "cash")
        pickup_type = request.data.get("pickup_type", "instant")
        pickup_time = request.data.get("pickup_time")
        notes = request.data.get("notes", "")
        pickup_by_other_person = request.data.get("pickup_by_other_person", False)
        pickup_person_name = request.data.get("pickup_person_name", "")
        pickup_person_phone = request.data.get("pickup_person_phone", "")

        if delivery_option == "delivery":
            pickup_type = "instant"
            pickup_time = None
            pickup_by_other_person = False
            pickup_person_name = ""
            pickup_person_phone = ""

        if pickup_type not in ("instant", "scheduled"):
            return Response({"error": "Invalid pickup type."}, status=400)

        parsed_pickup_time = None
        if pickup_type == "scheduled":
            if not pickup_time:
                return Response({"error": "Pickup time is required."}, status=400)
            parsed_pickup_time = parse_datetime(pickup_time)
            if not parsed_pickup_time:
                return Response({"error": "Invalid pickup time."}, status=400)
            if timezone.is_naive(parsed_pickup_time):
                parsed_pickup_time = timezone.make_aware(parsed_pickup_time)
            if parsed_pickup_time <= timezone.now():
                return Response({"error": "Pickup time must be in the future."}, status=400)

        # -------------------------------------------
        # Promotion selection
        # -------------------------------------------
        promotion_type = request.data.get("promotion_type")
        promotion_id = request.data.get("promotion_id")
        coupon_code = request.data.get("coupon_code")

        selected_discount = None
        selected_coupon = None

        if promotion_type == "discount" and promotion_id:
            try:
                selected_discount = Discount.objects.get(id=promotion_id, is_active=True)
            except Discount.DoesNotExist:
                return Response({"error": "Discount not found"}, status=400)
        elif promotion_type == "coupon" and coupon_code:
            try:
                selected_coupon = Coupon.objects.get(code=coupon_code, status='active')
            except Coupon.DoesNotExist:
                return Response({"error": "Coupon not found"}, status=400)

        # ============================================
        # 2. Estimate preparation time
        # ============================================
        active_orders = Order.objects.filter(
            shop=shop, status__in=["accepted", "preparing"]
        ).count()

        estimated_minutes = 20
        if active_orders >= 5:
            estimated_minutes = 25
        if active_orders >= 10:
            estimated_minutes = 30
        if active_orders >= 15:
            estimated_minutes = 35

        if pickup_type == "instant":
            estimated_ready_time = timezone.now() + timedelta(minutes=estimated_minutes)
        else:
            estimated_ready_time = parsed_pickup_time

        # ============================================
        # 3. Create the order skeleton
        # ============================================
        order = Order.objects.create(
            order_number=generate_online_order_number(shop),
            customer=request.user,
            shop=shop,
            customer_name=request.user.get_full_name() or request.user.username or request.user.phone,
            customer_phone=request.user.phone,
            payment_method=payment_method,
            payment_status="unpaid",
            order_type="online",
            pickup_type=pickup_type,
            pickup_time=parsed_pickup_time,
            notes=notes,
            status="pending",
            estimated_minutes=estimated_minutes,
            estimated_ready_time=estimated_ready_time,
            pickup_by_other_person=pickup_by_other_person,
            pickup_person_name=pickup_person_name,
            pickup_person_phone=pickup_person_phone,
            delivery_option=delivery_option,
            delivery_address=delivery_address if delivery_option == "delivery" else "",
            delivery_latitude=delivery_lat if delivery_option == "delivery" else None,
            delivery_longitude=delivery_lng if delivery_option == "delivery" else None,
            delivery_fee=Decimal("0.00"),
        )

        # ============================================
        # 4. Process the cart with OfferEngine
        # ============================================
        engine = OfferEngine(
            customer=request.user,
            shop=shop,
            coupon_code=coupon_code if selected_coupon else None,
            forced_discount=selected_discount,
        )

        cart_result = engine.calculate_cart(cart_items)

        original_amount = cart_result["original_total"]
        discount_amount = cart_result["discount_total"]
        final_amount = cart_result["final_total"]

        for item_result in cart_result["items"]:
            offer = item_result["offer"]
            cart_item = item_result["item"]
            OrderItem.objects.create(
                order=order,
                menu_item=cart_item.menu_item,
                discount=offer.discount,
                item_name=cart_item.menu_item.name,
                original_price=offer.original_price,
                discount_amount=offer.discount_amount,
                final_price=offer.final_price,
                quantity=cart_item.quantity,
                total_price=offer.final_price,
                discount_name=offer.discount_name,
                discount_percentage=offer.discount_value if offer.discount_type == "percentage" else None,
                promotion_type=offer.promotion_type,
            )

        # ============================================
        # 5. Save totals & promotion info
        # ============================================
        order.original_amount = original_amount
        order.discount_amount = discount_amount
        order.total_amount = final_amount
        order.discount = selected_discount
        order.coupon = selected_coupon

        if selected_discount:
            order.promotion_type = "discount"
            order.discount_name = selected_discount.name
        elif selected_coupon:
            order.promotion_type = "coupon"
        else:
            order.promotion_type = "none"

        order.save()

        # ============================================
        # 6. Record usage
        # ============================================
        if selected_discount:
            try:
                DiscountUsage.objects.create(
                    discount=selected_discount,
                    shop=shop,
                    order=order,
                    customer=request.user,
                    order_type="online",
                    discount_type=selected_discount.discount_type,
                    discount_value=selected_discount.value,
                    original_amount=original_amount,
                    discount_amount=discount_amount,
                    final_amount=final_amount,
                    quantity=cart_items.count(),
                )
            except IntegrityError:
                pass

        if selected_coupon:
            try:
                CouponUsage.objects.create(
                    coupon=selected_coupon,
                    customer=request.user,
                    shop=shop,
                    order=order,
                    order_type="online",
                    original_amount=original_amount,
                    discount_amount=discount_amount,
                    final_amount=final_amount,
                    quantity=cart_items.count(),
                )
            except IntegrityError:
                pass

        # ============================================
        # 7. Update customer stats
        # ============================================
        profile, created = CustomerProfile.objects.get_or_create(user=request.user)
        profile.total_orders += 1
        profile.save()

        # ============================================
        # 8. Notify shop manager (PUSH + WHATSAPP)
        # ============================================
        manager = User.objects.filter(
            role="manager",
            manager_profile__shop=shop
        ).first()

        # Push notification (existing)
        if manager and manager.fcm_token:
            send_push_notification(
                token=manager.fcm_token,
                title="🔥 New Order Received",
                body=f"Order #{order.order_number} ₹{order.total_amount}",
                data={
                    "type": "new_order",
                    "order_id": str(order.id),
                    "shop_id": str(shop.id),
                }
            )

        # ✅ WhatsApp notification to manager
        if manager and manager.phone:
            # Prepare pickup time display
            if order.pickup_type == "scheduled" and order.pickup_time:
                pickup_display = order.pickup_time.strftime("%d %b %I:%M %p")
            else:
                pickup_display = order.estimated_ready_time.strftime("%d %b %I:%M %p") if order.estimated_ready_time else "ASAP"

            try:
                WhatsAppService.send_manager_new_order(
                    manager_phone=manager.phone,
                    order_id=order.order_number,
                    customer_name=order.customer_name,
                    total=str(order.total_amount),
                    pickup_time=pickup_display
                )
            except Exception as e:
                logger.warning(f"Manager WhatsApp notification failed: {e}")

        # ============================================
        # 9. Clear the cart
        # ============================================
        cart_items.delete()

        return Response({
            "success": True,
            "message": "Order Placed Successfully",
            "order_id": order.id,
            "order_number": order.order_number,
            "total_amount": order.total_amount,
            "delivery_option": order.delivery_option,
            "delivery_address": order.delivery_address,
            "estimated_minutes": order.estimated_minutes,
            "estimated_ready_time": order.estimated_ready_time,
            "queue_count": active_orders,
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


# ==========================================
# ACCEPT ORDER VIEW (UPDATED WITH WHATSAPP)
# ==========================================

class AcceptOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = Order.objects.get(id=pk)
        order.status = "accepted"
        order.accepted_at = timezone.now()
        order.save()
        send_order_update(order)

        # Push notification (optional)
        if order.customer and order.customer.fcm_token:
            send_push_notification(
                token=order.customer.fcm_token,
                title="Order Accepted",
                body=f"Order #{order.order_number} accepted",
                data={"type": "order", "status": "accepted", "order_id": str(order.id)}
            )

        # WhatsApp notification to customer
        if order.customer and order.customer.phone:
            customer_name = order.customer.get_full_name() or order.customer.username or "Customer"
            prep_time = str(order.estimated_minutes)  # e.g., "20"
            try:
                WhatsAppService.send_order_accepted(
                    customer_phone=order.customer.phone,
                    customer_name=customer_name,
                    order_id=order.order_number,
                    prep_time_minutes=prep_time
                )
            except Exception as e:
                logger.warning(f"Order accepted WhatsApp failed: {e}")

        return Response({"message": "Order Accepted"})



# ==========================================
# REJECT ORDER VIEW (UPDATED WITH WHATSAPP)
# ==========================================

class RejectOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        reason = request.data.get("reason", "Order rejected")
        order = Order.objects.get(id=pk)
        order.status = "rejected"
        order.rejection_reason = reason
        order.save()
        send_order_update(order)

        # Update customer profile (if exists)
        if order.customer:
            profile = CustomerProfile.objects.get(user=order.customer)
            profile.total_rejected_orders += 1
            profile.trust_score -= 3
            if profile.trust_score < 50:
                profile.is_flagged = True
            profile.save()

        # Push notification
        if order.customer and order.customer.fcm_token:
            send_push_notification(
                token=order.customer.fcm_token,
                title="Order Rejected",
                body=reason,
                data={"type": "order", "status": "rejected", "order_id": str(order.id)}
            )

        # WhatsApp notification to customer
        if order.customer and order.customer.phone:
            try:
                WhatsAppService.send_order_rejected(
                    customer_phone=order.customer.phone,
                    order_id=order.order_number,
                    reason=reason
                )
            except Exception as e:
                logger.warning(f"Order rejected WhatsApp failed: {e}")

        return Response({"message": "Order Rejected"})


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


# ==========================================
# READY ORDER VIEW (UPDATED WITH WHATSAPP)
# ==========================================

class ReadyOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = Order.objects.get(id=pk)
        order.status = "ready"
        order.ready_at = timezone.now()
        order.save()
        send_order_update(order)

        # Push notification
        if order.customer and order.customer.fcm_token:
            send_push_notification(
                token=order.customer.fcm_token,
                title="Order Ready",
                body="Your order is ready for pickup",
                data={"type": "order", "status": "ready", "order_id": str(order.id)}
            )

        # WhatsApp notification to customer
        if order.customer and order.customer.phone:
            try:
                WhatsAppService.send_order_ready(
                    customer_phone=order.customer.phone,
                    order_id=order.order_number,
                    shop_name=order.shop.name
                )
            except Exception as e:
                logger.warning(f"Order ready WhatsApp failed: {e}")

        return Response({"message": "Order Ready"})


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


# ==========================================
# CANCEL ORDER VIEW (UPDATED WITH WHATSAPP)
# ==========================================

class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        order = Order.objects.get(id=pk, customer=request.user)
        if order.status not in ["pending", "accepted"]:
            return Response({"error": "Cannot cancel"}, status=400)

        order.status = "cancelled"
        order.save()
        send_order_update(order)

        # Update customer profile
        profile = CustomerProfile.objects.get(user=request.user)
        profile.total_cancelled_orders += 1
        profile.trust_score -= 10
        if profile.trust_score < 50:
            profile.is_flagged = True
        profile.save()

        # Notify manager via WhatsApp (if order was placed by customer)
        manager = User.objects.filter(role="manager", manager_profile__shop=order.shop).first()
        if manager and manager.phone:
            try:
                WhatsAppService.send_manager_order_cancelled(
                    manager_phone=manager.phone,
                    order_id=order.order_number,
                    customer_name=order.customer_name
                )
            except Exception as e:
                logger.warning(f"Manager cancellation WhatsApp failed: {e}")

        return Response({"message": "Order Cancelled"})


class PaymentReceivedView(APIView):

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

                shop=shop

            )

        except Order.DoesNotExist:

            return Response(
                {
                    "error": "Order not found"
                },
                status=404
            )

        # ----------------------------------
        # Already Paid
        # ----------------------------------

        if order.payment_status == "paid":

            return Response(
                {
                    "error": "Payment has already been received."
                },
                status=400
            )

        # ----------------------------------
        # Receive Payment
        # ----------------------------------

        order.payment_status = "paid"

        order.paid_at = timezone.now()

        order.save(
            update_fields=[
                "payment_status",
                "paid_at",
            ]
        )

        # ----------------------------------
        # Notify WebSocket
        # ----------------------------------

        send_order_update(order)

        # ----------------------------------
        # Notify Customer
        # ----------------------------------

        if (
            order.customer and
            order.customer.fcm_token
        ):

            send_push_notification(

                token=order.customer.fcm_token,

                title="Payment Received",

                body=(
                    f"Payment received for "
                    f"Order #{order.order_number}"
                ),

                data={
                    "type": "payment",
                    "status": "paid",
                    "order_id": str(order.id),
                }

            )

        serializer = OrderSerializer(order)

        return Response({

            "success": True,

            "message": "Payment received successfully.",

            "order": serializer.data

        })



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

        if not phone or len(phone) != 10:
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
            "name": f"{customer.first_name} {customer.last_name}",
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
    """
    Returns (customer, created) where created is True if a new customer was made.
    """
    if not phone:
        return None, False

    # ---------------------------------------
    # Normalize Phone
    # ---------------------------------------
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("+91"):
        clean_phone = phone[3:]
    elif phone.startswith("91"):
        clean_phone = phone[2:]
    else:
        clean_phone = phone

    full_phone = "+91" + clean_phone
    possible_numbers = [clean_phone, "91" + clean_phone, full_phone]

    # ---------------------------------------
    # Try to find existing customer
    # ---------------------------------------
    customer = User.objects.filter(role="customer", phone__in=possible_numbers).first()
    if customer:
        CustomerProfile.objects.get_or_create(
            user=customer,
            defaults={"trust_score": 100, "total_orders": 0}
        )
        return customer, False

    # ---------------------------------------
    # Create new customer (with lock)
    # ---------------------------------------
    with transaction.atomic():
        customer = User.objects.select_for_update().filter(
            role="customer", phone__in=possible_numbers
        ).first()
        if customer:
            CustomerProfile.objects.get_or_create(
                user=customer,
                defaults={"trust_score": 100, "total_orders": 0}
            )
            return customer, False

        # Generate unique username
        username = clean_phone
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{clean_phone}_{counter}"
            counter += 1

        customer = User(
            username=username,
            first_name=name or "Walk‑In Customer",
            phone=full_phone,
            role="customer",
            is_active=True,
            is_phone_verified=True,
        )
        customer.set_password(clean_phone)  # default password = phone number
        customer.save()

        CustomerProfile.objects.create(
            user=customer,
            trust_score=100,
            total_orders=0,
        )
        return customer, True

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
    
    
    
class CreateWalkInCartView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        # ------------------------------------
        # Permission
        # ------------------------------------

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # ------------------------------------
        # Manager Shop
        # ------------------------------------

        try:

            shop = request.user.manager_profile.shop

        except Exception:

            return Response(
                {
                    "error": "Manager shop not assigned"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ------------------------------------
        # Request Data
        # ------------------------------------

        customer_name = (
            request.data.get(
                "customer_name",
                "Walk-In Customer"
            ).strip()
        )

        customer_phone = (
            request.data.get(
                "customer_phone",
                ""
            ).strip()
        )

        payment_method = request.data.get(
            "payment_method",
            "cash"
        )

        payment_status = request.data.get(
            "payment_status",
            "unpaid"
        )

        notes = request.data.get(
            "notes",
            ""
        )

        # ------------------------------------
        # Validate Payment Method
        # ------------------------------------

        if payment_method not in [
            "cash",
            "upi",
        ]:

            payment_method = "cash"

        # ------------------------------------
        # Validate Payment Status
        # ------------------------------------

        if payment_status not in [
            "paid",
            "unpaid",
        ]:

            payment_status = "unpaid"

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
        # Create Draft Cart
        # Retry if duplicate cart number
        # ------------------------------------

        retries = 10

        while retries > 0:

            try:

                cart = WalkInCart.objects.create(

                    cart_number=generate_walkin_cart_number(shop),

                    manager=request.user,

                    shop=shop,

                    customer=None,

                    customer_name=customer_name,

                    customer_phone=customer_phone,

                    payment_method=payment_method,

                    payment_status=payment_status,

                    notes=notes,

                    status="draft",

                    total_amount=Decimal("0.00")

                )

                serializer = WalkInCartSerializer(cart)

                return Response(

                    serializer.data,

                    status=status.HTTP_201_CREATED

                )

            except IntegrityError:

                retries -= 1

        # ------------------------------------
        # Failed after retries
        # ------------------------------------

        return Response(

            {
                "error": "Unable to generate a unique cart number. Please try again."
            },

            status=status.HTTP_500_INTERNAL_SERVER_ERROR

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

        # --------------------------------------
        # Manager Permission
        # --------------------------------------

        if request.user.role != "manager":

            return Response(
                {
                    "error": "Permission denied"
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # --------------------------------------
        # Get Draft Cart
        # --------------------------------------

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

                status=status.HTTP_404_NOT_FOUND

            )

        # --------------------------------------
        # Read Request Data
        # --------------------------------------

        customer_name = request.data.get(

            "customer_name",

            cart.customer_name

        )

        customer_phone = request.data.get(

            "customer_phone",

            cart.customer_phone

        )

        payment_method = request.data.get(

            "payment_method",

            cart.payment_method

        )

        payment_status = request.data.get(

            "payment_status",

            cart.payment_status

        )

        notes = request.data.get(

            "notes",

            cart.notes

        )

        # --------------------------------------
        # Normalize Phone Number
        # --------------------------------------

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

        # --------------------------------------
        # Validate Payment Method
        # --------------------------------------

        if payment_method not in [

            "cash",

            "upi",

        ]:

            payment_method = "cash"

        # --------------------------------------
        # Validate Payment Status
        # --------------------------------------

        if payment_status not in [

            "paid",

            "unpaid",

        ]:

            payment_status = "unpaid"
        
                # --------------------------------------
        # Update Cart
        # --------------------------------------

        cart.customer_name = customer_name

        cart.customer_phone = customer_phone

        cart.payment_method = payment_method

        cart.payment_status = payment_status

        cart.notes = notes

        cart.save()

        # --------------------------------------
        # Return Updated Cart
        # --------------------------------------

        serializer = WalkInCartSerializer(cart)

        return Response(

            {
                "success": True,

                "message": "Draft cart updated successfully.",

                "cart": serializer.data

            },

            status=status.HTTP_200_OK

        )     


class PlaceWalkInCartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # 1. Only managers or super admins can place walk‑in orders
        if request.user.role not in ["manager", "super_admin"]:
            return Response({"error": "Permission denied"}, status=403)

        # 2. Fetch the draft cart
        try:
            cart = WalkInCart.objects.get(
                id=pk,
                manager=request.user if request.user.role == "manager" else None,
                status="draft"
            )
        except WalkInCart.DoesNotExist:
            return Response({"error": "Draft cart not found"}, status=404)

        if not cart.items.exists():
            return Response({"error": "Cart is empty"}, status=400)

        # ---------------------------------------------
        # Get or create customer from cart data
        # ---------------------------------------------
        customer, created = get_or_create_customer(
            cart.customer_phone,
            cart.customer_name
        )

        # ✅ If a new customer was created, send WhatsApp welcome
        if created and customer and customer.phone:
            try:
                WhatsAppService.send_welcome(
                    phone=customer.phone,
                    customer_name=customer.first_name or "Customer"
                )
            except Exception as e:
                logger.warning(f"Welcome WhatsApp failed for {customer.phone}: {e}")

        # Payment status
        payment_status = request.data.get("payment_status", "unpaid")
        if payment_status not in ["paid", "unpaid"]:
            return Response({"error": "Invalid payment status"}, status=400)

        paid_at = timezone.now() if payment_status == "paid" else None

        # ---------------------------------------------
        # Manual discount selection (optional)
        # ---------------------------------------------
        discount_id = request.data.get("discount_id", None)
        coupon_code = request.data.get("coupon_code", None)

        selected_discount = None
        selected_coupon = None

        if discount_id:
            try:
                selected_discount = Discount.objects.get(
                    id=discount_id,
                    shop=cart.shop,
                    is_active=True,
                    start_date__lte=timezone.now(),
                    end_date__gte=timezone.now()
                )
            except Discount.DoesNotExist:
                return Response({"error": "Invalid or inactive discount"}, status=400)

            # Ignore coupon if discount is manually selected
            coupon_code = None

        # ========================================================
        # 3. Create the order skeleton
        # ========================================================
        order = Order.objects.create(
            order_number=generate_walkin_order_number(cart.shop),
            customer=customer,   # now customer can be new or existing
            shop=cart.shop,
            payment_method=cart.payment_method,
            payment_status=payment_status,
            paid_at=paid_at,
            order_type="walkin",
            status="accepted",
            accepted_at=timezone.now(),
            customer_name=customer.first_name if customer else cart.customer_name,
            customer_phone=customer.phone if customer else cart.customer_phone,
            notes=cart.notes,
            total_amount=0,
            original_amount=0,
            discount_amount=0,
        )

        # ========================================================
        # 4. Apply discounts using OfferEngine
        # ========================================================
        engine = OfferEngine(
            customer=customer,
            shop=cart.shop,
            coupon_code=coupon_code,
            forced_discount=selected_discount,
        )

        original_total = Decimal("0.00")
        discount_total = Decimal("0.00")
        final_total = Decimal("0.00")

        for item in cart.items.all():
            if item.menu_item is None:
                item_price = Decimal(item.item_price) * item.quantity
                offer = OfferEngine.empty_result(price=item_price)
            else:
                offer = engine.get_best_offer(
                    menu_item=item.menu_item,
                    quantity=item.quantity,
                )

            original_total += offer.original_price
            discount_total += offer.discount_amount
            final_total += offer.final_price

            if offer.has_offer and offer.promotion_type == "discount":
                selected_discount = offer.discount
            elif offer.has_offer and offer.promotion_type == "coupon":
                selected_coupon = offer.coupon

            OrderItem.objects.create(
                order=order,
                menu_item=item.menu_item,
                discount=offer.discount if offer.promotion_type == "discount" else None,
                item_name=item.item_name,
                original_price=offer.original_price,
                discount_amount=offer.discount_amount,
                final_price=offer.final_price,
                quantity=item.quantity,
                total_price=offer.final_price,
                discount_name=offer.discount_name,
                discount_percentage=offer.discount_value
                if offer.discount_type == "percentage" else None,
                promotion_type=offer.promotion_type,
            )

        # Save totals and promotion info on the order
        order.original_amount = original_total
        order.discount_amount = discount_total
        order.total_amount = final_total
        order.discount = selected_discount
        order.coupon = selected_coupon

        if selected_discount:
            order.promotion_type = "discount"
            order.discount_name = selected_discount.name
        elif selected_coupon:
            order.promotion_type = "coupon"
        else:
            order.promotion_type = "none"
        order.save()

        # ========================================================
        # 5. Record usage (only if customer exists)
        # ========================================================
        if customer and selected_discount:
            try:
                DiscountUsage.objects.create(
                    discount=selected_discount,
                    shop=cart.shop,
                    order=order,
                    customer=customer,
                    order_type="walkin",
                    discount_type=selected_discount.discount_type,
                    discount_value=selected_discount.value,
                    original_amount=original_total,
                    discount_amount=discount_total,
                    final_amount=final_total,
                    quantity=cart.items.count(),
                )
            except IntegrityError:
                pass

        if customer and selected_coupon:
            try:
                CouponUsage.objects.create(
                    coupon=selected_coupon,
                    customer=customer,
                    shop=cart.shop,
                    order=order,
                    order_type="walkin",
                    original_amount=original_total,
                    discount_amount=discount_total,
                    final_amount=final_total,
                    quantity=cart.items.count(),
                )
            except IntegrityError:
                pass

        # ========================================================
        # 6. Update customer stats (only if customer exists)
        # ========================================================
        if customer:
            profile, created = CustomerProfile.objects.get_or_create(user=customer)
            profile.total_orders += 1
            profile.save()

        # ========================================================
        # 7. Notify frontend & mark cart as placed
        # ========================================================
        send_order_update(order)

        cart.status = "placed"
        cart.save()

        # Remove cart items after successful placement
        cart.items.all().delete()

        serializer = OrderSerializer(order)
        return Response({
            "success": True,
            "message": "Walk-In Order Created Successfully",
            "order": serializer.data,
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
        

from django.db.models import Q
from discounts.models import Discount
from discounts.coupon_models import Coupon
class CheckoutPreviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        shop_id = request.data.get("shop_id")
        promotion_type = request.data.get("promotion_type")
        promotion_id = request.data.get("promotion_id")
        coupon_code = request.data.get("coupon_code")

        if not shop_id:
            return Response({"error": "Shop ID required"}, status=400)

        try:
            shop = Shop.objects.get(id=shop_id, is_active=True)
        except Shop.DoesNotExist:
            return Response({"error": "Shop not found"}, status=404)

        try:
            cart = Cart.objects.get(customer=request.user)
        except Cart.DoesNotExist:
            return Response({"error": "Cart not found"}, status=400)

        cart_items = CartItem.objects.filter(cart=cart)
        if not cart_items.exists():
            return Response({"error": "Cart empty"}, status=400)

        selected_discount = None
        selected_coupon = None

        if promotion_type == "discount" and promotion_id:
            try:
                selected_discount = Discount.objects.get(id=promotion_id, is_active=True)
            except Discount.DoesNotExist:
                return Response({"error": "Discount not found"}, status=400)
        elif promotion_type == "coupon" and coupon_code:
            try:
                selected_coupon = Coupon.objects.get(code=coupon_code, status='active')
            except Coupon.DoesNotExist:
                return Response({"error": "Coupon not found"}, status=400)

        engine = OfferEngine(
            customer=request.user,
            shop=shop,
            coupon_code=coupon_code if selected_coupon else None,
            forced_discount=selected_discount,
        )

        # Use calculate_cart to get rounded totals and adjusted item discounts
        result = engine.calculate_cart(cart_items)

        # Find applied promotion name and type from first item that has an offer
        applied_discount_name = None
        applied_discount_type = None
        message = None

        for item_result in result["items"]:
            offer = item_result["offer"]
            if offer.promotion_type == "discount":
                applied_discount_name = offer.discount.name if offer.discount else None
                applied_discount_type = "discount"
                break
            elif offer.promotion_type == "coupon":
                applied_discount_name = offer.coupon.code if offer.coupon else None
                applied_discount_type = "coupon"
                break

        # Get the first message if any offer failed
        for item_result in result["items"]:
            if not item_result["offer"].has_offer and item_result["offer"].message:
                message = item_result["offer"].message
                break

        # Build per‑item breakdown for frontend
        items_breakdown = []
        for item_result in result["items"]:
            offer = item_result["offer"]
            items_breakdown.append({
                "item_name": item_result["item"].menu_item.name,
                "original_price": offer.original_price,
                "discount_amount": offer.discount_amount,
                "final_price": offer.final_price,
            })

        return Response({
            "original_total": result["original_total"],
            "discount_amount": result["discount_total"],
            "final_total": result["final_total"],
            "discount_type": applied_discount_type,
            "discount_name": applied_discount_name,
            "message": message,
            "items": items_breakdown,   # <-- added for per‑item display
        })
        
        
class AvailablePromotionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        shop_id = request.query_params.get('shop_id')
        if not shop_id:
            return Response({"error": "shop_id required"}, status=400)

        now = timezone.now()

        # Discounts
        discounts = Discount.objects.filter(
            Q(shop_id=shop_id) | Q(shop__isnull=True),
            is_active=True,
            start_date__lte=now,
            end_date__gte=now,
        )

        # Coupons
        coupons = Coupon.objects.filter(
            Q(shop_id=shop_id) | Q(shop__isnull=True),
            status='active',
            start_date__lte=now,
            end_date__gte=now,
        )

        # Debug: print counts
        print(f"Discounts: {discounts.count()}, Coupons: {coupons.count()}")

        promotions = []
        for d in discounts:
            promotions.append({
                "id": d.id,
                "type": "discount",
                "name": d.name,
                "description": d.description,
                "discount_type": d.discount_type,
                "value": d.value,
                "code": None,
                "apply_on": d.apply_on,
                "minimum_order": d.minimum_order_amount,
            })
        for c in coupons:
            promotions.append({
                "id": c.id,
                "type": "coupon",
                "name": c.name,
                "description": c.description,
                "discount_type": c.discount_type,
                "value": c.value,
                "code": c.code,          # ← important: include the code
                "apply_on": None,        # coupons have no apply_on
                "minimum_order": c.minimum_order_amount,
            })

        return Response({"promotions": promotions})
    

# Add to orders/views.py (at the end of the file)
from django.views import View
from django.http import HttpResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .receipt_utils import (
    QR_SUPPORT,
    generate_receipt_text, 
    generate_receipt_data, 
    generate_receipt_pdf,
    generate_qr_code,
    PDF_SUPPORT
)
import logging

logger = logging.getLogger(__name__)

# ==========================================
# RECEIPT GENERATION VIEWS
# ==========================================

class GenerateReceiptView(APIView):
    """
    Generate receipt for an order (online or walk-in)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        # Check permission
        if request.user.role not in ['manager', 'super_admin']:
            # Customers can view their own receipts
            try:
                order = Order.objects.get(id=pk, customer=request.user)
            except Order.DoesNotExist:
                return Response(
                    {'error': 'Order not found or access denied'},
                    status=status.HTTP_403_FORBIDDEN
                )
        else:
            # Managers can view any order in their shop
            try:
                shop = request.user.manager_profile.shop
                order = Order.objects.get(id=pk, shop=shop)
            except Exception:
                return Response(
                    {'error': 'Order not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        bill_type = request.GET.get('bill_type', 'standard')
        receipt_data = generate_receipt_data(order, bill_type)
        
        # Add QR code for digital receipts
        if QR_SUPPORT:
            receipt_data['qr_code'] = generate_qr_code(order)
        
        return Response(receipt_data, status=status.HTTP_200_OK)



@method_decorator(csrf_exempt, name='dispatch')
class DownloadReceiptPDFView(View):
    def get(self, request, pk):
        # ---- Authentication ----
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return HttpResponse('Authentication required.', status=401, content_type='text/plain')
        try:
            token = auth_header[7:] if auth_header.startswith('Bearer ') else auth_header
            access_token = AccessToken(token)
            user = User.objects.get(id=access_token['user_id'])
        except Exception:
            return HttpResponse('Invalid token.', status=401, content_type='text/plain')

        # ---- Permission ----
        try:
            if user.role not in ['manager', 'super_admin']:
                order = Order.objects.get(id=pk, customer=user)
            else:
                shop = user.manager_profile.shop
                order = Order.objects.get(id=pk, shop=shop)
        except Order.DoesNotExist:
            return HttpResponse('Order not found.', status=404, content_type='text/plain')
        except Exception:
            return HttpResponse('Access denied.', status=403, content_type='text/plain')

        bill_type = request.GET.get('bill_type', 'standard')

        # ---- Generate PDF ----
        try:
            pdf_bytes = generate_receipt_pdf(order, bill_type)
            # Ensure bytes
            if not isinstance(pdf_bytes, bytes):
                pdf_bytes = bytes(pdf_bytes)

            # Validate PDF
            if not pdf_bytes.startswith(b'%PDF'):
                # Last resort: return plain text
                text = generate_receipt_text(order, bill_type)
                response = HttpResponse(text, content_type='text/plain; charset=utf-8')
                response['Content-Disposition'] = f'attachment; filename="receipt_{order.order_number}.txt"'
                return response

            # Success – return PDF
            response = HttpResponse(pdf_bytes, content_type='application/pdf')
            # ✅ Use order number in filename
            response['Content-Disposition'] = f'attachment; filename="invoice_{order.order_number}.pdf"'
            response['Content-Length'] = str(len(pdf_bytes))
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response

        except Exception as e:
            # Fallback to text on any error
            text = generate_receipt_text(order, bill_type)
            response = HttpResponse(text, content_type='text/plain; charset=utf-8')
            response['Content-Disposition'] = f'attachment; filename="receipt_{order.order_number}.txt"'
            return response
        
        

class PrintReceiptView(APIView):
    """
    Print receipt directly - Available ONLY for Managers
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        # ONLY managers can print
        if request.user.role not in ['manager', 'super_admin']:
            return Response(
                {'error': 'Permission denied. Only managers can print receipts.'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            shop = request.user.manager_profile.shop
            order = Order.objects.get(id=pk, shop=shop)
        except Exception:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        bill_type = request.data.get('bill_type', 'standard')
        receipt_text = generate_receipt_text(order, bill_type)
        
        return Response({
            'success': True,
            'receipt_text': receipt_text,
            'receipt_data': generate_receipt_data(order, bill_type)
        })



@method_decorator(csrf_exempt, name='dispatch')
class DownloadReceiptTextView(View):
    """
    Download receipt as text file - Available ONLY for Managers
    """
    
    def get(self, request, pk):
        # Get token from Authorization header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return HttpResponse(
                'Authentication credentials were not provided.',
                status=401,
                content_type='text/plain'
            )
        
        # Extract token
        try:
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
            else:
                token = auth_header
        except Exception:
            return HttpResponse(
                'Invalid authentication format.',
                status=401,
                content_type='text/plain'
            )
        
        # Verify token and get user
        try:
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(id=user_id)
        except Exception:
            return HttpResponse(
                'Invalid token',
                status=401,
                content_type='text/plain'
            )
        
        # ONLY managers can download text
        if user.role not in ['manager', 'super_admin']:
            return HttpResponse(
                'Permission denied. Only managers can download text receipts.',
                status=403,
                content_type='text/plain'
            )

        # Get the order
        try:
            shop = user.manager_profile.shop
            order = Order.objects.get(id=pk, shop=shop)
        except Exception:
            return HttpResponse(
                'Order not found',
                status=404,
                content_type='text/plain'
            )

        bill_type = request.GET.get('bill_type', 'standard')
        receipt_text = generate_receipt_text(order, bill_type)
        
        response = HttpResponse(receipt_text, content_type='text/plain; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="receipt_{order.order_number}.txt"'
        return response


class BulkPrintReceiptsView(APIView):
    """
    Print multiple receipts at once - Available ONLY for Managers
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # ONLY managers can bulk print
        if request.user.role not in ['manager', 'super_admin']:
            return Response(
                {'error': 'Permission denied. Only managers can bulk print.'},
                status=status.HTTP_403_FORBIDDEN
            )

        order_ids = request.data.get('order_ids', [])
        if not order_ids:
            return Response(
                {'error': 'No order IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            shop = request.user.manager_profile.shop
            orders = Order.objects.filter(id__in=order_ids, shop=shop)
        except Exception:
            return Response(
                {'error': 'Orders not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        bill_type = request.data.get('bill_type', 'standard')
        receipts = []
        for order in orders:
            receipts.append({
                'order_number': order.order_number,
                'receipt_text': generate_receipt_text(order, bill_type),
                'total_amount': float(order.total_amount),
            })

        return Response({
            'success': True,
            'count': len(receipts),
            'receipts': receipts
        })


class AvailableBillTypesView(APIView):
    """
    Get available bill types - Available for all authenticated users
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bill_types = [
            {'id': 'standard', 'name': 'Standard Bill', 'description': 'Regular bill format', 'icon': '📄'},
            {'id': 'detailed', 'name': 'Detailed Bill', 'description': 'Detailed breakdown with discounts', 'icon': '📊'},
            {'id': 'compact', 'name': 'Compact Bill', 'description': 'Compact format for thermal printer', 'icon': '📋'},
        ]
        
        return Response({
            'bill_types': bill_types
        })
        

# orders/views.py - Add this for inline preview

@method_decorator(csrf_exempt, name='dispatch')
class ViewReceiptPDFView(View):
    """
    View receipt PDF inline in the browser (for testing)
    """
    
    def get(self, request, pk):
        # --- Authentication (same as before) ---
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return HttpResponse('Authentication required.', status=401, content_type='text/plain')
        
        try:
            if auth_header.startswith('Bearer '):
                token = auth_header[7:]
            else:
                token = auth_header
            access_token = AccessToken(token)
            user_id = access_token['user_id']
            user = User.objects.get(id=user_id)
        except Exception:
            return HttpResponse('Invalid token.', status=401, content_type='text/plain')
        
        # --- Permission check ---
        try:
            if user.role not in ['manager', 'super_admin']:
                order = Order.objects.get(id=pk, customer=user)
            else:
                shop = user.manager_profile.shop
                order = Order.objects.get(id=pk, shop=shop)
        except Order.DoesNotExist:
            return HttpResponse('Order not found.', status=404, content_type='text/plain')
        except Exception:
            return HttpResponse('Access denied.', status=403, content_type='text/plain')
        
        # --- Get bill type ---
        bill_type = request.GET.get('bill_type', 'standard')
        
        try:
            # Generate PDF (returns bytes)
            pdf_bytes = generate_receipt_pdf(order, bill_type)
            
            # If we got text (fallback), return as text
            if isinstance(pdf_bytes, str):
                response = HttpResponse(pdf_bytes, content_type='text/plain; charset=utf-8')
                response['Content-Disposition'] = f'attachment; filename="receipt_{order.order_number}.txt"'
                return response
            
            # Ensure we have bytes
            if not isinstance(pdf_bytes, bytes):
                pdf_bytes = bytes(pdf_bytes)
            
            # Validate PDF signature
            if not pdf_bytes.startswith(b'%PDF'):
                # Not a valid PDF, return text
                text_receipt = generate_receipt_text(order, bill_type)
                response = HttpResponse(text_receipt, content_type='text/plain; charset=utf-8')
                response['Content-Disposition'] = f'attachment; filename="receipt_{order.order_number}.txt"'
                return response
            
            # --- Return PDF with proper headers ---
            response = HttpResponse(
                pdf_bytes,
                content_type='application/pdf',
                status=200
            )
            # Force download as attachment
            response['Content-Disposition'] = f'attachment; filename="receipt_{order.order_number}.pdf"'
            response['Content-Length'] = str(len(pdf_bytes))
            # Prevent any caching or transformation
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            # Ensure binary transfer
            response['Content-Transfer-Encoding'] = 'binary'
            
            return response
        
        except Exception as e:
            return HttpResponse(
                f'PDF generation error: {str(e)}',
                status=500,
                content_type='text/plain'
            )
            

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Order
from .serializers import OrderSerializer
from accounts.permissions import IsSuperAdmin
from rest_framework.pagination import PageNumberPagination

         
class SuperAdminOrderListView(generics.ListAPIView):
    """
    Super Admin endpoint to list all orders with filtering & pagination.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = OrderSerializer
    pagination_class = PageNumberPagination
    pagination_class.page_size = 15                    # default items per page
    pagination_class.page_size_query_param = 'page_size'  # allow frontend to set
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'order_type', 'payment_status', 'shop__id']
    search_fields = ['order_number', 'customer__phone', 'customer__first_name', 'customer__last_name']
    ordering_fields = ['ordered_at', 'total_amount', 'status']
    ordering = ['-ordered_at']

    def get_queryset(self):
        queryset = Order.objects.select_related('shop', 'customer').prefetch_related('items')
        # Optional date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(ordered_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(ordered_at__date__lte=end_date)
        return queryset