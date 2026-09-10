# delivery/views.py

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.exceptions import ValidationError
from rest_framework.generics import RetrieveAPIView
from django.utils import timezone
import re

from orders.models import Order
from shops.models import Shop
from accounts.models import User
from .models import (
    DeliveryBoyProfile, DeliveryAssignment, Parcel,
    DeliveryLocation, WalkInTokenCounter, DeliveryBoyOTP
)
from .serializers import (
    DeliveryBoyProfileSerializer, DeliveryBoyProfileDetailSerializer,
    DeliveryAssignmentSerializer, ParcelSerializer,
    DeliveryLocationSerializer, WalkInTokenCounterSerializer, DeliveryBoyLoginSerializer
)
from .permissions import (
    IsDeliveryBoy, IsManagerOrSuperAdmin, IsOwnShopManager, IsOwnDeliveryBoy
)
from .services import (
    validate_delivery_location, create_parcel_for_order,
    assign_delivery_manually, auto_assign_delivery,
    scan_parcel, confirm_pickup, confirm_out_for_delivery,
    confirm_delivery, haversine_distance
)
from orders.serializers import OrderSerializer
from .permissions import IsDeliveryBoy
from accounts.models import User
import random


from django.conf import settings
from whatsapp.services import WhatsAppService
import logging

logger = logging.getLogger(__name__)


# ============================================================
# NEW: Auth Views for Delivery Boy
# ============================================================

class DeliveryBoyRequestOTPView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        raw_phone = request.data.get('phone')
        if not raw_phone:
            return Response({'error': 'Phone number is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Normalize phone variants (with and without +91 / 91)
        clean_digits = ''.join(filter(str.isdigit, str(raw_phone)))
        phone_variants = [raw_phone.strip()]
        if len(clean_digits) == 10:
            phone_variants.extend([f"+91{clean_digits}", clean_digits, f"91{clean_digits}"])
        elif len(clean_digits) == 12 and clean_digits.startswith('91'):
            phone_variants.extend([f"+{clean_digits}", clean_digits[2:], clean_digits])

        # Check if delivery boy exists
        user = User.objects.filter(phone__in=phone_variants, role='delivery_boy').first()
        if not user:
            return Response({
                'error': f"No delivery boy found with phone number '{raw_phone}'. Please verify in Django Admin that an account exists with Role='Delivery Boy'."
            }, status=status.HTTP_404_NOT_FOUND)

        # Target phone for WhatsApp (ensure standard international format e.g. +91XXXXXXXXXX)
        target_phone = user.phone if user.phone.startswith('+') else (f"+91{user.phone}" if len(user.phone) == 10 else f"+{user.phone}")

        # Generate OTP
        otp_obj = DeliveryBoyOTP.generate_otp(user.phone)

        # Send OTP via WhatsApp
        whatsapp_sent = False
        whatsapp_error = None
        try:
            WhatsAppService.send_otp(target_phone, otp_obj.otp_code)
            whatsapp_sent = True
            logger.info(f"WhatsApp OTP sent to delivery boy {target_phone}")
        except Exception as e:
            whatsapp_error = str(e)
            logger.error(f"Failed to send WhatsApp OTP to {target_phone}: {e}")

        resp_data = {
            'message': 'OTP sent to your WhatsApp successfully.' if whatsapp_sent else 'OTP generated, but WhatsApp delivery failed.',
            'phone': user.phone,
            'whatsapp_sent': whatsapp_sent,
        }
        if not whatsapp_sent and whatsapp_error:
            resp_data['whatsapp_error'] = whatsapp_error

        # In DEBUG mode, return OTP in response for testing
        if getattr(settings, 'DEBUG', False):
            resp_data['dev_otp'] = otp_obj.otp_code

        # If WhatsApp failed and not in DEBUG, return 500 so frontend knows
        status_code = status.HTTP_200_OK if (whatsapp_sent or getattr(settings, 'DEBUG', False)) else status.HTTP_500_INTERNAL_SERVER_ERROR
        return Response(resp_data, status=status_code)


class DeliveryBoyLoginView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DeliveryBoyLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if 'otp_obj' in data:
            # OTP login
            user = data['user']
            data['otp_obj'].used = True
            data['otp_obj'].save(update_fields=['used'])
        else:
            user = data['user']

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': {
                'id': user.id,
                'phone': user.phone,
                'role': user.role,
                'username': user.username,
            }
        }, status=status.HTTP_200_OK)


# ============================================================
#  DELIVERY BOY PROFILE VIEWS
# ============================================================

class DeliveryBoyProfileViewSet(viewsets.ModelViewSet):
    queryset = DeliveryBoyProfile.objects.all()
    serializer_class = DeliveryBoyProfileSerializer
    permission_classes = [IsAuthenticated, IsManagerOrSuperAdmin | IsDeliveryBoy]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return DeliveryBoyProfile.objects.all()
        elif user.role == 'manager':
            shop = user.manager_profile.shop
            return DeliveryBoyProfile.objects.filter(shop=shop)
        elif user.role == 'delivery_boy':
            return DeliveryBoyProfile.objects.filter(user=user)
        return DeliveryBoyProfile.objects.none()

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return DeliveryBoyProfileDetailSerializer
        return DeliveryBoyProfileSerializer

    def perform_create(self, serializer):
        user = self.request.user
        request_data = self.request.data

        phone = request_data.get('phone')
        full_name = request_data.get('full_name')
        max_active_orders = request_data.get('max_active_orders', 3)

        if not phone or not full_name:
            raise ValidationError({"phone": "This field is required."} if not phone else {"full_name": "This field is required."})

        phone = re.sub(r'[\s\-]', '', phone)
        if not phone.startswith('+'):
            phone = '+91' + phone

        try:
            delivery_user = User.objects.get(phone=phone)
            if delivery_user.role != 'delivery_boy':
                delivery_user.role = 'delivery_boy'
                delivery_user.save(update_fields=['role'])
        except User.DoesNotExist:
            username = phone.replace('+', '')
            base_username = username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}_{counter}"
                counter += 1

            delivery_user = User(
                username=username,
                phone=phone,
                role='delivery_boy',
                is_active=True,
                is_phone_verified=True,
            )
            delivery_user.set_password(phone)
            name_parts = full_name.split(' ', 1)
            delivery_user.first_name = name_parts[0]
            if len(name_parts) > 1:
                delivery_user.last_name = name_parts[1]
            delivery_user.save()

        if user.role == 'manager':
            shop = user.manager_profile.shop
            if not shop:
                raise ValidationError({"shop": "Manager has no shop assigned."})
        elif user.role == 'super_admin':
            shop_id = request_data.get('shop')
            if not shop_id:
                raise ValidationError({"shop": "This field is required for super_admin."})
            try:
                shop = Shop.objects.get(id=shop_id)
            except Shop.DoesNotExist:
                raise ValidationError({"shop": "Invalid shop ID."})
        else:
            raise ValidationError({"detail": "Not authorized to create delivery boy."})

        if DeliveryBoyProfile.objects.filter(user=delivery_user).exists():
            raise ValidationError({"phone": "A delivery boy profile already exists for this user."})

        serializer.save(
            user=delivery_user,
            shop=shop,
            full_name=full_name,
            phone=phone,
            max_active_orders=max_active_orders,
        )

    @action(detail=True, methods=['post'])
    def toggle_online(self, request, pk=None):
        profile = self.get_object()
        if request.user.role == 'delivery_boy' and profile.user != request.user:
            return Response({'error': 'You can only update your own status.'}, status=status.HTTP_403_FORBIDDEN)

        profile.is_online = not profile.is_online
        if not profile.is_online:
            profile.is_available = False
        else:
            # When going online, set available if has capacity
            profile.is_available = profile.has_capacity
        profile.save(update_fields=['is_online', 'is_available'])
        return Response(DeliveryBoyProfileSerializer(profile).data)

    @action(detail=True, methods=['post'])
    def toggle_available(self, request, pk=None):
        profile = self.get_object()
        if request.user.role == 'delivery_boy' and profile.user != request.user:
            return Response({'error': 'You can only update your own status.'}, status=status.HTTP_403_FORBIDDEN)

        if not profile.is_online:
            return Response({'error': 'Cannot set available while offline.'}, status=status.HTTP_400_BAD_REQUEST)

        # If trying to set available but already at capacity, prevent it
        if not profile.is_available and not profile.has_capacity:
            return Response({'error': 'Cannot set available. Delivery boy is at max active orders.'}, status=status.HTTP_400_BAD_REQUEST)

        profile.is_available = not profile.is_available
        profile.save(update_fields=['is_available'])
        return Response(DeliveryBoyProfileSerializer(profile).data)


# ============================================================
#  DELIVERY ASSIGNMENT VIEWS
# ============================================================

class DeliveryAssignmentViewSet(viewsets.ModelViewSet):
    queryset = DeliveryAssignment.objects.all()
    serializer_class = DeliveryAssignmentSerializer
    permission_classes = [IsAuthenticated, IsManagerOrSuperAdmin | IsDeliveryBoy]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return DeliveryAssignment.objects.all()
        elif user.role == 'manager':
            shop = user.manager_profile.shop
            return DeliveryAssignment.objects.filter(shop=shop)
        elif user.role == 'delivery_boy':
            profile = get_object_or_404(DeliveryBoyProfile, user=user)
            return DeliveryAssignment.objects.filter(delivery_boy=profile)
        return DeliveryAssignment.objects.none()

    @action(detail=False, methods=['post'])
    def assign(self, request):
        order_id = request.data.get('order_id')
        delivery_boy_id = request.data.get('delivery_boy_id')

        if not order_id or not delivery_boy_id:
            return Response({'error': 'order_id and delivery_boy_id are required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(Order, id=order_id)
        delivery_boy = get_object_or_404(DeliveryBoyProfile, id=delivery_boy_id)

        user = request.user
        if user.role == 'manager':
            if user.manager_profile.shop != order.shop:
                return Response({'error': 'You can only assign orders from your shop.'},
                                status=status.HTTP_403_FORBIDDEN)
            if delivery_boy.shop != order.shop:
                return Response({'error': 'Delivery boy does not belong to your shop.'},
                                status=status.HTTP_400_BAD_REQUEST)
        elif user.role != 'super_admin':
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            assignment = assign_delivery_manually(order, delivery_boy)
            return Response(DeliveryAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def auto_assign(self, request):
        order_id = request.data.get('order_id')

        if not order_id:
            return Response({'error': 'order_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(Order, id=order_id)

        user = request.user
        if user.role == 'manager':
            if user.manager_profile.shop != order.shop:
                return Response({'error': 'You can only auto-assign orders from your shop.'},
                                status=status.HTTP_403_FORBIDDEN)
        elif user.role != 'super_admin':
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            assignment = auto_assign_delivery(order)
            return Response(DeliveryAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def accept(self, request, pk=None):
        assignment = self.get_object()
        if request.user.role != 'delivery_boy':
            return Response({'error': 'Only delivery boys can accept assignments.'},
                            status=status.HTTP_403_FORBIDDEN)

        if assignment.delivery_boy.user != request.user:
            return Response({'error': 'This assignment is not for you.'},
                            status=status.HTTP_403_FORBIDDEN)

        if assignment.status != 'assigned':
            return Response({'error': f'Cannot accept. Current status: {assignment.status}'},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            assignment.status = 'accepted'
            assignment.accepted_at = timezone.now()
            assignment.save(update_fields=['status', 'accepted_at'])

        return Response(DeliveryAssignmentSerializer(assignment).data)

    @action(detail=True, methods=['post'])
    def pickup(self, request, pk=None):
        assignment = self.get_object()
        if request.user.role != 'delivery_boy':
            return Response({'error': 'Only delivery boys can confirm pickup.'},
                            status=status.HTTP_403_FORBIDDEN)

        delivery_boy = get_object_or_404(DeliveryBoyProfile, user=request.user)

        try:
            assignment = confirm_pickup(assignment, delivery_boy)
            return Response(DeliveryAssignmentSerializer(assignment).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def out_for_delivery(self, request, pk=None):
        assignment = self.get_object()
        if request.user.role != 'delivery_boy':
            return Response({'error': 'Only delivery boys can update status.'},
                            status=status.HTTP_403_FORBIDDEN)

        delivery_boy = get_object_or_404(DeliveryBoyProfile, user=request.user)

        try:
            assignment = confirm_out_for_delivery(assignment, delivery_boy)
            return Response(DeliveryAssignmentSerializer(assignment).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def deliver(self, request, pk=None):
        assignment = self.get_object()
        if request.user.role != 'delivery_boy':
            return Response({'error': 'Only delivery boys can confirm delivery.'},
                            status=status.HTTP_403_FORBIDDEN)

        delivery_boy = get_object_or_404(DeliveryBoyProfile, user=request.user)

        try:
            assignment = confirm_delivery(assignment, delivery_boy)
            return Response(DeliveryAssignmentSerializer(assignment).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
#  PARCEL VIEWS
# ============================================================

class ParcelViewSet(viewsets.ModelViewSet):
    queryset = Parcel.objects.all()
    serializer_class = ParcelSerializer
    permission_classes = [IsAuthenticated, IsManagerOrSuperAdmin | IsDeliveryBoy]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return Parcel.objects.all()
        elif user.role == 'manager':
            shop = user.manager_profile.shop
            return Parcel.objects.filter(shop=shop)
        elif user.role == 'delivery_boy':
            profile = get_object_or_404(DeliveryBoyProfile, user=user)
            return Parcel.objects.filter(
                delivery_assignment__delivery_boy=profile
            )
        return Parcel.objects.none()

    @action(detail=False, methods=['post'])
    def scan(self, request):
        qr_token = request.data.get('qr_token')
        if not qr_token:
            return Response({'error': 'qr_token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        if request.user.role != 'delivery_boy':
            return Response({'error': 'Only delivery boys can scan QR codes.'},
                            status=status.HTTP_403_FORBIDDEN)

        delivery_boy = get_object_or_404(DeliveryBoyProfile, user=request.user)

        try:
            parcel, assignment = scan_parcel(qr_token, delivery_boy)
            return Response({
                'parcel': ParcelSerializer(parcel).data,
                'assignment': DeliveryAssignmentSerializer(assignment).data,
                'order': {
                    'order_number': parcel.order.order_number,
                    'customer_name': parcel.order.customer_name,
                    'customer_phone': parcel.order.customer_phone,
                    'delivery_address': parcel.order.delivery_address,
                    'total_amount': str(parcel.order.total_amount),
                }
            })
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ============================================================
#  GPS LOCATION VIEWS
# ============================================================

class DeliveryLocationViewSet(viewsets.ModelViewSet):
    queryset = DeliveryLocation.objects.all()
    serializer_class = DeliveryLocationSerializer
    permission_classes = [IsAuthenticated, IsDeliveryBoy | IsManagerOrSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'super_admin':
            return DeliveryLocation.objects.all()
        elif user.role == 'manager':
            shop = user.manager_profile.shop
            return DeliveryLocation.objects.filter(delivery_boy__shop=shop)
        elif user.role == 'delivery_boy':
            profile = get_object_or_404(DeliveryBoyProfile, user=user)
            return DeliveryLocation.objects.filter(delivery_boy=profile)
        return DeliveryLocation.objects.none()

    def create(self, request, *args, **kwargs):
        if request.user.role != 'delivery_boy':
            return Response({'error': 'Only delivery boys can update location.'},
                            status=status.HTTP_403_FORBIDDEN)

        delivery_boy = get_object_or_404(DeliveryBoyProfile, user=request.user)

        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')

        if not latitude or not longitude:
            return Response({'error': 'latitude and longitude are required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        delivery_boy.update_location(latitude, longitude)

        location = DeliveryLocation.objects.create(
            delivery_boy=delivery_boy,
            assignment=request.data.get('assignment'),
            latitude=latitude,
            longitude=longitude,
            accuracy=request.data.get('accuracy'),
            speed=request.data.get('speed'),
        )

        return Response(DeliveryLocationSerializer(location).data, status=status.HTTP_201_CREATED)


# ============================================================
#  DELIVERY STATISTICS VIEWS
# ============================================================

class DeliveryStatisticsView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagerOrSuperAdmin]

    def get(self, request):
        user = request.user

        if user.role == 'super_admin':
            assignments = DeliveryAssignment.objects.filter(status='delivered')
            boys = DeliveryBoyProfile.objects.all()
        elif user.role == 'manager':
            shop = user.manager_profile.shop
            assignments = DeliveryAssignment.objects.filter(shop=shop, status='delivered')
            boys = DeliveryBoyProfile.objects.filter(shop=shop)
        else:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        from .models import get_business_date
        today = get_business_date()

        total_completed = assignments.count()
        total_distance = sum(float(a.estimated_distance_km or 0) for a in assignments)

        today_assignments = assignments.filter(delivered_at__date=today)
        today_completed = today_assignments.count()
        today_distance = sum(float(a.estimated_distance_km or 0) for a in today_assignments)

        week_ago = timezone.now() - timezone.timedelta(days=7)
        week_assignments = assignments.filter(delivered_at__gte=week_ago)
        week_completed = week_assignments.count()
        week_distance = sum(float(a.estimated_distance_km or 0) for a in week_assignments)

        month_ago = timezone.now() - timezone.timedelta(days=30)
        month_assignments = assignments.filter(delivered_at__gte=month_ago)
        month_completed = month_assignments.count()
        month_distance = sum(float(a.estimated_distance_km or 0) for a in month_assignments)

        avg_distance = total_distance / total_completed if total_completed > 0 else 0

        data = {
            'total': {
                'completed': total_completed,
                'distance_km': round(total_distance, 2),
            },
            'today': {
                'completed': today_completed,
                'distance_km': round(today_distance, 2),
            },
            'weekly': {
                'completed': week_completed,
                'distance_km': round(week_distance, 2),
            },
            'monthly': {
                'completed': month_completed,
                'distance_km': round(month_distance, 2),
            },
            'average': {
                'distance_km': round(avg_distance, 2),
            },
            'delivery_boys': DeliveryBoyProfileSerializer(boys, many=True).data,
        }

        return Response(data)


# ============================================================
#  DASHBOARD VIEWS
# ============================================================

class DeliveryDashboardView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated, IsManagerOrSuperAdmin]

    def get(self, request):
        user = request.user

        if user.role == 'super_admin':
            assignments = DeliveryAssignment.objects.filter(status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery'])
            boys = DeliveryBoyProfile.objects.filter(is_online=True)
        elif user.role == 'manager':
            shop = user.manager_profile.shop
            assignments = DeliveryAssignment.objects.filter(shop=shop, status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery'])
            boys = DeliveryBoyProfile.objects.filter(shop=shop, is_online=True)
        else:
            return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)

        active = []
        for assignment in assignments:
            active.append({
                'assignment': DeliveryAssignmentSerializer(assignment).data,
                'order': {
                    'order_number': assignment.order.order_number,
                    'customer_name': assignment.order.customer_name,
                    'customer_phone': assignment.order.customer_phone,
                },
                'delivery_boy': {
                    'id': assignment.delivery_boy.id,
                    'full_name': assignment.delivery_boy.full_name,
                    'current_latitude': str(assignment.delivery_boy.current_latitude),
                    'current_longitude': str(assignment.delivery_boy.current_longitude),
                    'last_location_at': assignment.delivery_boy.last_location_at,
                }
            })

        return Response({
            'active_deliveries': active,
            'online_boys': DeliveryBoyProfileSerializer(boys, many=True).data,
        })


# ============================================================
#  READY ORDERS FOR DELIVERY
# ============================================================

class ReadyOrdersForDeliveryView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsManagerOrSuperAdmin]
    serializer_class = OrderSerializer

    def get_queryset(self):
        user = self.request.user

        if user.role == 'manager':
            shop = user.manager_profile.shop
        elif user.role == 'super_admin':
            shop_id = self.request.query_params.get('shop_id')
            shop = get_object_or_404(Shop, id=shop_id) if shop_id else None
        else:
            return Order.objects.none()

        if not shop:
            return Order.objects.none()

        return Order.objects.filter(
            shop=shop,
            status='ready',
            delivery_option='delivery'
        ).exclude(
            delivery_assignment__status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery']
        ).select_related('shop')
        
        
class OrderTrackingView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            assignment = DeliveryAssignment.objects.get(
                order_id=order_id,
                status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery', 'delivered']
            )
        except DeliveryAssignment.DoesNotExist:
            return Response({'error': 'No active delivery assignment for this order.'}, status=404)

        boy = assignment.delivery_boy
        order = assignment.order

        data = {
            'order_id': order.id,
            'order_number': order.order_number,
            'status': assignment.status,
            'delivery_boy': {
                'id': boy.id,
                'full_name': boy.full_name,
                'phone': boy.phone,
                'latitude': str(boy.current_latitude) if boy.current_latitude else None,
                'longitude': str(boy.current_longitude) if boy.current_longitude else None,
                'last_location_at': boy.last_location_at,
            },
            'shop': {
                'latitude': str(order.shop.latitude) if order.shop.latitude else None,
                'longitude': str(order.shop.longitude) if order.shop.longitude else None,
                'name': order.shop.name,
            },
            'customer_location': {
                'latitude': str(order.delivery_latitude) if order.delivery_latitude else None,
                'longitude': str(order.delivery_longitude) if order.delivery_longitude else None,
                'address': order.delivery_address,
            },
        }
        return Response(data)