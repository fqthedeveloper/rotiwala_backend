from firebase_admin import auth

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated
from .models import User
from .models import CustomerProfile
from .serializers import UserSerializer
from .models import ManagerProfile
from rest_framework import generics, status
from .serializers import ManagerSerializer
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from .permissions import IsSuperAdmin
from orders.models import Order, OrderItem
from shops.models import Shop
from menu.models import MenuItem
from accounts.models import User, CustomerProfile
from django.db.models.functions import TruncDate




class CustomerRegisterView(APIView):

    permission_classes = []

    def post(self, request):

        token = request.data.get("token")

        first_name = request.data.get(
            "first_name",
            ""
        )

        last_name = request.data.get(
            "last_name",
            ""
        )

        password = request.data.get(
            "password"
        )

        if not token:

            return Response(
                {
                    "error": "Firebase token required"
                },
                status=400
            )

        try:

            decoded = auth.verify_id_token(
                token,
                clock_skew_seconds=60
            )

            firebase_uid = decoded["uid"]

            phone = decoded.get(
                "phone_number"
            )

            if not phone:

                return Response(
                    {
                        "error": "Phone number not found"
                    },
                    status=400
                )

            if not password:

                return Response(
                    {
                        "error": "Password is required"
                    },
                    status=400
                )

            if len(password) < 6:

                return Response(
                    {
                        "error": "Password must be at least 6 characters"
                    },
                    status=400
                )

            if User.objects.filter(
                phone=phone
            ).exists():

                return Response(
                    {
                        "error": "Mobile number already registered"
                    },
                    status=400
                )

            user = User.objects.create_user(
                username=phone,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                password=password,
                firebase_uid=firebase_uid,
                role="customer",
                is_phone_verified=True
            )

            CustomerProfile.objects.create(
                user=user
            )

            refresh = RefreshToken.for_user(
                user
            )

            return Response(
                {
                    "message": "Registration successful",
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": UserSerializer(user).data
                }
            )

        except Exception as e:

            return Response(
                {
                    "error": str(e)
                },
                status=400
            )
            


class FirebaseLoginView(APIView):

    permission_classes = []

    def post(self, request):

        token = request.data.get("token")

        if not token:
            return Response(
                {
                    "error": "Firebase token required"
                },
                status=400
            )

        try:

            decoded = auth.verify_id_token(
                token,
                clock_skew_seconds=60
            )

            firebase_uid = decoded["uid"]
            phone = decoded.get("phone_number")

            if not phone:
                return Response(
                    {
                        "error": "Phone number not found"
                    },
                    status=400
                )

            try:

                user = User.objects.get(
                    phone=phone
                )

            except User.DoesNotExist:

                return Response(
                    {
                        "error": "This mobile number is not registered. Please register first."
                    },
                    status=400
                )

            if user.firebase_uid:

                if user.firebase_uid != firebase_uid:

                    return Response(
                        {
                            "error": "Account mismatch"
                        },
                        status=400
                    )

            else:

                user.firebase_uid = firebase_uid
                user.save()

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                    "user": UserSerializer(user).data
                }
            )

        except Exception as e:

            return Response(
                {
                    "error": str(e)
                },
                status=400
            )
            


class PasswordLoginView(APIView):

    permission_classes = []

    def post(self, request):

        phone = request.data.get("phone", "").strip()
        password = request.data.get("password", "").strip()

        # Validate input
        if not phone:
            return Response(
                {
                    "success": False,
                    "field": "phone",
                    "message": "Phone number is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if not password:
            return Response(
                {
                    "success": False,
                    "field": "password",
                    "message": "Password is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check phone exists
        try:
            user = User.objects.get(phone=phone)

        except User.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "field": "phone",
                    "message": "This phone number is not registered."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Check account active
        if not user.is_active:
            return Response(
                {
                    "success": False,
                    "message": "Your account has been disabled. Please contact support."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Verify password
        auth_user = authenticate(
            username=user.username,
            password=password
        )

        if not auth_user:
            return Response(
                {
                    "success": False,
                    "field": "password",
                    "message": "Incorrect password. Please try again."
                },
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Generate JWT
        refresh = RefreshToken.for_user(auth_user)

        return Response(
            {
                "success": True,
                "message": f"Welcome back {auth_user.first_name or auth_user.username}!",
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(auth_user).data
            },
            status=status.HTTP_200_OK
        )


class SaveFCMTokenView(APIView):

    permission_classes = [
        IsAuthenticated
    ]

    def post(self, request):

        token = request.data.get(
            "token"
        )

        request.user.fcm_token = token

        request.user.save()

        return Response({

            "message":
            "FCM Token Saved"
        })
        

class ManagerListView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def get(self, request):

        managers = User.objects.filter(
            role="manager"
        )

        serializer = ManagerSerializer(
                managers,
                many=True
            )

        return Response(
            serializer.data
        )


class CreateManagerView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def post(self, request):

        user = User.objects.create_user(
            username=request.data["phone"],
            phone=request.data["phone"],
            first_name=request.data["first_name"],
            last_name=request.data["last_name"],
            email=request.data.get(
                "email"
            ),
            password=request.data[
                "password"
            ],
            role="manager"
        )

        ManagerProfile.objects.create(
            user=user,
            full_name=f"{user.first_name} {user.last_name}",
            phone=user.phone
        )

        return Response({
            "message":
            "Manager Created"
        })
        
        

class ManagerDetailView(
    generics.RetrieveUpdateDestroyAPIView
):

    queryset = User.objects.filter(
        role="manager"
    )

    serializer_class = UserSerializer

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def update(
        self,
        request,
        *args,
        **kwargs
    ):

        manager = self.get_object()

        manager.first_name = request.data.get(
                "first_name"
            )

        manager.last_name = request.data.get(
                "last_name"
            )

        manager.phone = request.data.get(
                "phone"
            )

        manager.email = request.data.get(
                "email"
            )

        manager.username = manager.phone

        manager.save()

        profile = manager.manager_profile

        profile.full_name = (
            f"{manager.first_name} "
            f"{manager.last_name}"
        )

        profile.phone = manager.phone

        profile.shop_id = request.data.get(
                "shop_id"
            ) or None

        profile.save()

        password = request.data.get(
                "password"
            )

        if password:

            manager.set_password(
                password
            )

            manager.save()

        return Response({
            "message":
            "Manager Updated"
        })


class AssignManagerView(APIView):

    permission_classes = [
        IsAuthenticated,
        IsSuperAdmin
    ]

    def post(self, request):

        manager_id = request.data.get(
                "manager_id"
            )

        shop_id = request.data.get(
                "shop_id"
            )

        profile = ManagerProfile.objects.get(
                user_id=manager_id
            )

        profile.shop_id = shop_id

        profile.save()

        return Response({
            "message":
            "Manager Assigned"
        })
        
        
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from .models import User, CustomerProfile, CustomerFlag
from .serializers import CustomerListSerializer, CustomerProfileSerializer, CustomerFlagSerializer
from .permissions import IsSuperAdmin, IsSuperAdminOrManagerOrSelf
from orders.models import Order
from rest_framework.exceptions import PermissionDenied
from .utils import manager_can_access_customer

        
class CustomerListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsSuperAdminOrManagerOrSelf]
    serializer_class = CustomerListSerializer
    pagination_class = None

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.filter(role='customer').select_related('customerprofile').prefetch_related('customer_flags')

        if user.role == 'super_admin':
            # Apply search and filters
            search = self.request.query_params.get('search')
            if search:
                queryset = queryset.filter(
                    Q(username__icontains=search) |
                    Q(phone__icontains=search) |
                    Q(email__icontains=search) |
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search)
                )
            is_active = self.request.query_params.get('is_active')
            if is_active is not None:
                queryset = queryset.filter(is_active=is_active.lower() == 'true')
            is_flagged = self.request.query_params.get('is_flagged')
            if is_flagged is not None:
                queryset = queryset.filter(customerprofile__is_flagged=is_flagged.lower() == 'true')
            return queryset.order_by('-date_joined')

        elif user.role == 'manager':
            shop = getattr(user.manager_profile, 'shop', None)
            if shop:
                customer_ids = Order.objects.filter(shop=shop).values_list('customer_id', flat=True).distinct()
                queryset = queryset.filter(id__in=customer_ids)
            else:
                queryset = queryset.none()
            # optional search/filter ...
            return queryset.order_by('-date_joined')

        # Customer role: no list
        return queryset.none()
    
    

class CustomerDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated, IsSuperAdminOrManagerOrSelf]
    serializer_class = CustomerProfileSerializer
    queryset = User.objects.filter(role='customer').select_related('customerprofile').prefetch_related('customer_flags')

    def update(self, request, *args, **kwargs):
        user = self.get_object()

        # Customer updating their own profile – only allow safe fields
        if request.user.role == 'customer' and request.user == user:
            allowed_fields = ['first_name', 'last_name', 'phone', 'email']
            for field in allowed_fields:
                if field in request.data:
                    setattr(user, field, request.data[field])
            user.save()
            return Response({'message': 'Profile updated successfully'})

        # Super admin / manager: update is_active (or other admin fields)
        is_active = request.data.get('is_active')
        if is_active is not None:
            user.is_active = bool(is_active)
            user.save()
            return Response({'message': f"User {'blocked' if not is_active else 'unblocked'} successfully"})

        return Response({'message': 'User updated successfully'})
    
    
class CustomerSelfProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CustomerProfileSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        user = self.get_object()
        # Only allow safe fields
        allowed_fields = ['first_name', 'last_name', 'phone', 'email']
        for field in allowed_fields:
            if field in request.data:
                setattr(user, field, request.data[field])
        user.save()
        return Response({'message': 'Profile updated successfully'})
    

class CustomerFlagCreateView(generics.CreateAPIView):
    """
    POST /api/accounts/customers/<id>/flag/
    Body: { "reason": "..." }
    Super admin only.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = CustomerFlagSerializer

    def perform_create(self, serializer):
        user_id = self.kwargs.get('customer_id')
        customer = User.objects.get(id=user_id, role='customer')
        profile, _ = CustomerProfile.objects.get_or_create(user=customer)
        # Create flag
        serializer.save(customer=customer, flagged_by=self.request.user)
        # Update profile is_flagged = True
        profile.is_flagged = True
        profile.save()


class CustomerFlagDeleteView(generics.DestroyAPIView):
    """
    DELETE /api/accounts/customers/<id>/flag/<flag_id>/
    Super admin only.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def delete(self, request, *args, **kwargs):
        customer_id = kwargs.get('customer_id')
        flag_id = kwargs.get('flag_id')
        try:
            flag = CustomerFlag.objects.get(id=flag_id, customer_id=customer_id)
            flag.delete()
            # Check if any flags remain
            remaining = CustomerFlag.objects.filter(customer_id=customer_id).exists()
            if not remaining:
                CustomerProfile.objects.filter(user_id=customer_id).update(is_flagged=False)
            return Response({'message': 'Flag removed'}, status=status.HTTP_204_NO_CONTENT)
        except CustomerFlag.DoesNotExist:
            return Response({'error': 'Flag not found'}, status=status.HTTP_404_NOT_FOUND)


class CustomerToggleBlockView(generics.UpdateAPIView):
    """
    PATCH /api/accounts/customers/<id>/toggle-block/
    Body: { "is_active": true/false }
    Super admin only.
    """
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def patch(self, request, *args, **kwargs):
        user_id = kwargs.get('customer_id')
        try:
            user = User.objects.get(id=user_id, role='customer')
        except User.DoesNotExist:
            return Response({'error': 'Customer not found'}, status=status.HTTP_404_NOT_FOUND)
        is_active = request.data.get('is_active')
        if is_active is None:
            return Response({'error': 'is_active field required'}, status=status.HTTP_400_BAD_REQUEST)
        user.is_active = bool(is_active)
        user.save()
        return Response({'message': f"User {'blocked' if not is_active else 'unblocked'} successfully"})
    


class CustomerFlagCreateView(generics.CreateAPIView):
    permission_classes = [IsAuthenticated]  # remove IsSuperAdmin, we'll check manually
    serializer_class = CustomerFlagSerializer

    def perform_create(self, serializer):
        user = self.request.user
        customer_id = self.kwargs.get('customer_id')
        try:
            customer = User.objects.get(id=customer_id, role='customer')
        except User.DoesNotExist:
            raise PermissionDenied("Customer not found")

        # Allow super admin or manager (if customer belongs to their shop)
        if user.role == 'super_admin':
            pass
        elif user.role == 'manager' and manager_can_access_customer(user, customer):
            pass
        else:
            raise PermissionDenied("You are not allowed to flag this customer")

        profile, _ = CustomerProfile.objects.get_or_create(user=customer)
        serializer.save(customer=customer, flagged_by=user)
        profile.is_flagged = True
        profile.save()
        

class CustomerFlagDeleteView(generics.DestroyAPIView):
    permission_classes = [IsAuthenticated]  # remove IsSuperAdmin

    def delete(self, request, *args, **kwargs):
        customer_id = kwargs.get('customer_id')
        flag_id = kwargs.get('flag_id')
        try:
            flag = CustomerFlag.objects.get(id=flag_id, customer_id=customer_id)
        except CustomerFlag.DoesNotExist:
            return Response({'error': 'Flag not found'}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        # Allow super admin or the flag creator (if manager)
        if user.role == 'super_admin' or (user.role == 'manager' and flag.flagged_by == user):
            flag.delete()
            # Update profile if no flags remain
            if not CustomerFlag.objects.filter(customer_id=customer_id).exists():
                CustomerProfile.objects.filter(user_id=customer_id).update(is_flagged=False)
            return Response({'message': 'Flag removed'}, status=status.HTTP_204_NO_CONTENT)
        else:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        
        
# ---------- Super Admin Dashboard Stats ----------
class SuperAdminDashboardStatsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        # Aggregations across all shops
        total_orders = Order.objects.count()
        total_revenue = Order.objects.filter(status='completed').aggregate(total=Sum('total_amount'))['total'] or 0
        total_customers = User.objects.filter(role='customer').count()
        total_shops = Shop.objects.filter(is_active=True).count()
        total_products = MenuItem.objects.filter(is_available=True).count()

        pending_orders = Order.objects.filter(status='pending').count()
        completed_orders = Order.objects.filter(status='completed').count()
        cancelled_orders = Order.objects.filter(status='cancelled').count()

        today = timezone.now().date()
        orders_today = Order.objects.filter(ordered_at__date=today).count()
        revenue_today = Order.objects.filter(
            ordered_at__date=today,
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # Week
        start_of_week = today - timedelta(days=today.weekday())
        orders_this_week = Order.objects.filter(ordered_at__date__gte=start_of_week).count()
        revenue_this_week = Order.objects.filter(
            ordered_at__date__gte=start_of_week,
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        # Month
        start_of_month = today.replace(day=1)
        orders_this_month = Order.objects.filter(ordered_at__date__gte=start_of_month).count()
        revenue_this_month = Order.objects.filter(
            ordered_at__date__gte=start_of_month,
            status='completed'
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        data = {
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'total_customers': total_customers,
            'total_shops': total_shops,
            'total_products': total_products,
            'pending_orders': pending_orders,
            'completed_orders': completed_orders,
            'cancelled_orders': cancelled_orders,
            'orders_today': orders_today,
            'revenue_today': revenue_today,
            'orders_this_week': orders_this_week,
            'revenue_this_week': revenue_this_week,
            'orders_this_month': orders_this_month,
            'revenue_this_month': revenue_this_month,
        }
        return Response(data)


# ---------- Recent Orders ----------
class SuperAdminRecentOrdersView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        limit = int(request.query_params.get('limit', 10))
        orders = Order.objects.select_related('shop', 'customer').order_by('-ordered_at')[:limit]
        data = []
        for order in orders:
            data.append({
                'id': order.id,
                'shop_name': order.shop.name,
                'customer_name': order.customer.get_full_name() if order.customer else order.customer_name or 'Guest',
                'total': order.total_amount,
                'status': order.status,
                'created_at': order.ordered_at,
            })
        return Response(data)


# ---------- Revenue Trend (daily) ----------
class SuperAdminRevenueTrendView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days-1)

        # Use ORM to get daily revenue for completed orders
        # We'll group by date using TruncDate
        trend = (
            Order.objects.filter(
                ordered_at__date__gte=start_date,
                ordered_at__date__lte=end_date,
                status='completed'
            )
            .annotate(date=TruncDate('ordered_at'))
            .values('date')
            .annotate(revenue=Sum('total_amount'))
            .order_by('date')
        )

        # Fill missing dates with zero
        date_range = [start_date + timedelta(days=i) for i in range(days)]
        result = []
        trend_dict = {item['date']: item['revenue'] for item in trend}
        for d in date_range:
            result.append({
                'date': d.strftime('%Y-%m-%d'),
                'revenue': float(trend_dict.get(d, 0)),
            })
        return Response(result)


# ---------- Orders by Shop ----------
class SuperAdminOrdersByShopView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        shops = Shop.objects.annotate(
            order_count=Count('order'),
            revenue=Sum('order__total_amount', filter=Q(order__status='completed'))
        ).values('name', 'order_count', 'revenue')

        data = []
        for shop in shops:
            data.append({
                'shop_name': shop['name'],
                'order_count': shop['order_count'],
                'revenue': float(shop['revenue'] or 0),
            })
        return Response(data)


# ---------- Top Selling Products ----------
class SuperAdminTopProductsView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        limit = int(request.query_params.get('limit', 6))
        # Aggregate total quantity sold per menu item across all orders
        top = (
            OrderItem.objects
            .values('menu_item_id', 'menu_item__name')
            .annotate(total_quantity=Sum('quantity'))
            .order_by('-total_quantity')[:limit]
        )

        data = []
        for item in top:
            data.append({
                'id': item['menu_item_id'],
                'name': item['menu_item__name'],
                'total_quantity': item['total_quantity'],
            })
        return Response(data)