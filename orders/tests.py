from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal

from accounts.models import User, ManagerProfile, PreparingStaffProfile
from shops.models import Shop
from menu.models import MenuItem, MenuCategory
from orders.models import Order, OrderItem, WalkInCart, WalkInCartItem
from orders.token_utils import assign_walkin_token, get_display_screen_tokens


class PreparingStaffAndTokenTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        # Create shop
        self.shop = Shop.objects.create(
            name="Roti Wala Central",
            shop_code="RWC01",
            phone="9876543210",
            address="123 Main St",
        )

        # Create manager
        self.manager = User.objects.create_user(
            username="manager_test",
            phone="9000000001",
            password="password123",
            role="manager",
        )
        self.manager.manager_profile.shop = self.shop
        self.manager.manager_profile.save()

        # Create preparing staff
        self.prep_staff = User.objects.create_user(
            username="prep_staff_test",
            phone="9000000002",
            password="password123",
            role="preparing_staff",
        )
        self.prep_staff.preparing_staff_profile.shop = self.shop
        self.prep_staff.preparing_staff_profile.save()

        # Create menu category and item
        self.category = MenuCategory.objects.create(name="Rotis")
        self.menu_item = MenuItem.objects.create(
            shop=self.shop,
            name="Butter Roti",
            base_price=Decimal("15.00"),
            category=self.category,
            is_available=True,
        )

    def test_user_staff_shop_property(self):
        """Test staff_shop returns assigned shop for manager and preparing staff."""
        self.assertEqual(self.manager.staff_shop, self.shop)
        self.assertEqual(self.prep_staff.staff_shop, self.shop)

    def test_preparing_staff_profile_creation_signal(self):
        """Test that creating a user with role=preparing_staff auto-creates PreparingStaffProfile."""
        staff_user = User.objects.create_user(
            username="new_staff",
            phone="9000000003",
            password="password123",
            role="preparing_staff",
            first_name="John",
            last_name="Cook",
        )
        self.assertTrue(hasattr(staff_user, "preparing_staff_profile"))
        self.assertEqual(staff_user.role, "preparing_staff")

    def test_walkin_order_token_assignment(self):
        """Test that walk-in orders are automatically assigned sequential daily tokens."""
        # Create draft cart
        cart = WalkInCart.objects.create(
            cart_number="CART-001",
            manager=self.manager,
            shop=self.shop,
            customer_name="Walk-in Ravi",
            customer_phone="9876540001",
            status="draft",
        )
        WalkInCartItem.objects.create(
            cart=cart,
            menu_item=self.menu_item,
            item_name=self.menu_item.name,
            item_price=self.menu_item.base_price,
            quantity=2,
        )

        # Place cart as preparing staff
        self.client.force_authenticate(user=self.prep_staff)
        res = self.client.post(f"/api/orders/walkin/cart/{cart.id}/place/", {"payment_status": "paid"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data["success"])
        self.assertIsNotNone(res.data["token_number"])
        self.assertEqual(res.data["token_number"], "0001")

        order = Order.objects.get(id=res.data["order"]["id"])
        self.assertEqual(order.token_number, "0001")
        self.assertEqual(order.order_type, "walkin")
        self.assertIsNotNone(order.business_date)

        # Place a second walk-in order to verify token increments
        cart2 = WalkInCart.objects.create(
            cart_number="CART-002",
            manager=self.manager,
            shop=self.shop,
            customer_name="Walk-in Sita",
            customer_phone="9876540002",
            status="draft",
        )
        WalkInCartItem.objects.create(
            cart=cart2,
            menu_item=self.menu_item,
            item_name=self.menu_item.name,
            item_price=self.menu_item.base_price,
            quantity=1,
        )
        res2 = self.client.post(f"/api/orders/walkin/cart/{cart2.id}/place/", {"payment_status": "paid"})
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(res2.data["token_number"], "0002")

    def test_preparing_staff_order_workflow(self):
        """Test preparing staff viewing, readying, and completing orders."""
        order = Order.objects.create(
            order_number="ORD-TEST-101",
            shop=self.shop,
            order_type="walkin",
            status="accepted",
            payment_status="paid",
            total_amount=Decimal("30.00"),
        )
        assign_walkin_token(order)

        self.client.force_authenticate(user=self.prep_staff)

        # 1. Preparing staff can view shop orders
        res_list = self.client.get("/api/orders/staff/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_list.data), 1)

        # 2. Preparing staff marks order as ready
        res_ready = self.client.post(f"/api/orders/{order.id}/ready/")
        self.assertEqual(res_ready.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, "ready")

        # 3. Check display screen shows order as READY
        res_display = self.client.get(f"/api/orders/display-screen/?shop_id={self.shop.id}")
        self.assertEqual(res_display.status_code, status.HTTP_200_OK)
        ready_tokens = [item["token_number"] for item in res_display.data["ready"]]
        self.assertIn(order.token_number, ready_tokens)

        # 4. Preparing staff hands over / completes order
        res_collect = self.client.post(f"/api/orders/{order.id}/collected/")
        self.assertEqual(res_collect.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, "collected")

    def test_token_quick_action_endpoint(self):
        """Test TokenOrderActionView ready and complete by token number."""
        order = Order.objects.create(
            order_number="ORD-TEST-102",
            shop=self.shop,
            order_type="walkin",
            status="preparing",
            payment_status="paid",
            total_amount=Decimal("50.00"),
        )
        token = assign_walkin_token(order)

        self.client.force_authenticate(user=self.prep_staff)

        # Action: Ready by token
        res_ready = self.client.post("/api/orders/token-action/", {
            "token_number": token,
            "action": "ready",
        })
        self.assertEqual(res_ready.status_code, status.HTTP_200_OK)
        self.assertEqual(res_ready.data["status"], "ready")

        # Action: Complete by token
        res_complete = self.client.post("/api/orders/token-action/", {
            "token_number": token,
            "action": "complete",
        })
        self.assertEqual(res_complete.status_code, status.HTTP_200_OK)
        self.assertEqual(res_complete.data["status"], "collected")

    def test_live_display_screen_html_view(self):
        """Test that the live TV display board HTML view renders with 200 OK."""
        res = self.client.get(f"/api/orders/display/{self.shop.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, self.shop.name)
        self.assertContains(res, "Ready for Pickup")

    def test_manager_preparing_staff_management_workflow(self):
        """Test manager adding, viewing, deactivating, and resetting staff password."""
        # 1. Manager adds a new staff member
        self.client.force_authenticate(user=self.manager)
        res_create = self.client.post("/api/accounts/preparing-staff/", {
            "full_name": "Ramesh Kitchen",
            "phone": "9998887771",
            "password": "initialPass123",
        })
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        new_staff_id = res_create.data["profile"]["id"]

        # 2. Manager views list of preparing staff (multiple staff supported)
        res_list = self.client.get("/api/accounts/preparing-staff/")
        self.assertEqual(res_list.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res_list.data) >= 2)  # self.prep_staff and Ramesh

        # 3. Manager deactivates Ramesh
        res_deact = self.client.patch(f"/api/accounts/preparing-staff/{new_staff_id}/", {
            "is_active": False,
        }, format="json")
        self.assertEqual(res_deact.status_code, status.HTTP_200_OK)
        self.assertFalse(res_deact.data["is_active"])

        # 4. Deactivated staff cannot login
        self.client.force_authenticate(user=None)
        res_login = self.client.post("/api/accounts/password-login/", {
            "phone": "+919998887771",
            "password": "initialPass123",
        })
        self.assertEqual(res_login.status_code, status.HTTP_403_FORBIDDEN)

        # 5. Manager re-activates staff and resets password
        self.client.force_authenticate(user=self.manager)
        res_react = self.client.patch(f"/api/accounts/preparing-staff/{new_staff_id}/", {
            "is_active": True,
            "password": "newSecurePass123",
        }, format="json")
        self.assertEqual(res_react.status_code, status.HTTP_200_OK)
        self.assertTrue(res_react.data["is_active"])

        # 6. Activated staff logs in with new password
        self.client.force_authenticate(user=None)
        res_login_ok = self.client.post("/api/accounts/password-login/", {
            "phone": "+919998887771",
            "password": "newSecurePass123",
        })
        self.assertEqual(res_login_ok.status_code, status.HTTP_200_OK)
        self.assertTrue(res_login_ok.data["success"])

    def test_staff_dashboard_and_self_profile(self):
        """Test preparing staff viewing dashboard and self profile."""
        self.client.force_authenticate(user=self.prep_staff)

        # 1. Staff self profile
        res_me = self.client.get("/api/accounts/preparing-staff/me/")
        self.assertEqual(res_me.status_code, status.HTTP_200_OK)
        self.assertEqual(res_me.data["shop_name"], self.shop.name)

        # 2. Staff updates self profile name
        res_patch_me = self.client.patch("/api/accounts/preparing-staff/me/", {
            "full_name": "Senior Prep Chef",
        })
        self.assertEqual(res_patch_me.status_code, status.HTTP_200_OK)
        self.assertEqual(res_patch_me.data["full_name"], "Senior Prep Chef")

        # 3. Staff accesses kitchen dashboard stats
        res_dash = self.client.get("/api/orders/dashboard/")
        self.assertEqual(res_dash.status_code, status.HTTP_200_OK)
        self.assertIn("pending", res_dash.data)
        self.assertIn("ready", res_dash.data)
        self.assertEqual(res_dash.data["shop_name"], self.shop.name)

    def test_bidirectional_staff_salary_sync(self):
        """
        Verify bidirectional synchronization between accounts.PreparingStaffProfile
        and expenses.Staff:
        1. Created via /api/accounts/preparing-staff/ -> appears in /api/expenses/staff/
        2. Created via /api/expenses/staff/ -> automatically creates preparing staff login account
        3. Updating in expenses updates profile; deactivating in profile updates expenses.
        """
        self.client.force_authenticate(user=self.manager)

        # 1. Manager creates a kitchen preparing staff member with monthly salary
        res_create_kitchen = self.client.post("/api/accounts/preparing-staff/", {
            "full_name": "Suresh Maharaj",
            "phone": "9888877771",
            "password": "sureshPassword123",
            "monthly_salary": "16500.00",
        })
        self.assertEqual(res_create_kitchen.status_code, status.HTTP_201_CREATED)

        # Check expenses staff list: Suresh must be present with salary
        res_staff_list = self.client.get("/api/expenses/staff/")
        self.assertEqual(res_staff_list.status_code, status.HTTP_200_OK)
        suresh_expense = next((s for s in res_staff_list.data if s["phone"] == "9888877771"), None)
        self.assertIsNotNone(suresh_expense)
        self.assertEqual(suresh_expense["name"], "Suresh Maharaj")
        self.assertEqual(Decimal(str(suresh_expense["monthly_salary"])), Decimal("16500.00"))
        self.assertTrue(suresh_expense["has_kitchen_login"])

        # 2. Manager adds salary payment for Suresh in expenses
        res_salary_pay = self.client.post("/api/expenses/staff/salary/add/", {
            "staff_id": suresh_expense["id"],
            "amount": "5000.00",
            "payment_date": "2026-09-11",
            "payment_method": "CASH",
            "payment_type": "ADVANCE",
            "notes": "Advance given",
        })
        self.assertEqual(res_salary_pay.status_code, status.HTTP_201_CREATED)

        # 3. Manager creates a staff member from the Expenses / Payroll module
        res_create_salary_staff = self.client.post("/api/expenses/staff/", {
            "name": "Gopal Kitchen Helper",
            "phone": "9888877772",
            "monthly_salary": "14000.00",
            "is_active": True,
            "password": "gopalLoginPass123",
        })
        self.assertEqual(res_create_salary_staff.status_code, status.HTTP_201_CREATED)
        gopal_id = res_create_salary_staff.data["id"]

        # 4. Verify Gopal automatically shows up in Kitchen Preparing Staff management
        res_kitchen_list = self.client.get("/api/accounts/preparing-staff/")
        self.assertEqual(res_kitchen_list.status_code, status.HTTP_200_OK)
        gopal_kitchen = next((k for k in res_kitchen_list.data if k["phone"] == "9888877772"), None)
        self.assertIsNotNone(gopal_kitchen)
        self.assertEqual(gopal_kitchen["full_name"], "Gopal Kitchen Helper")
        self.assertEqual(Decimal(str(gopal_kitchen["monthly_salary"])), Decimal("14000.00"))

        # 5. Gopal can immediately log in to kitchen system with the set password
        self.client.force_authenticate(user=None)
        res_gopal_login = self.client.post("/api/accounts/password-login/", {
            "phone": "+919888877772",
            "password": "gopalLoginPass123",
        })
        self.assertEqual(res_gopal_login.status_code, status.HTTP_200_OK)
        self.assertEqual(res_gopal_login.data["user"]["role"], "preparing_staff")

        # 6. Manager updates Gopal's name and salary via expenses
        self.client.force_authenticate(user=self.manager)
        res_update_gopal = self.client.patch(f"/api/expenses/staff/{gopal_id}/", {
            "name": "Gopal Senior Head",
            "monthly_salary": "18000.00",
        })
        self.assertEqual(res_update_gopal.status_code, status.HTTP_200_OK)

        # Check kitchen profile is synced with new name
        res_kitchen_updated = self.client.get("/api/accounts/preparing-staff/")
        gopal_synced = next((k for k in res_kitchen_updated.data if k["phone"] == "9888877772"), None)
        self.assertEqual(gopal_synced["full_name"], "Gopal Senior Head")

    def test_auto_delivery_assignment_on_order_ready(self):
        """
        Verify that when an order transitions to 'ready' for a shop with
        delivery_assignment_mode='auto', it automatically creates parcel
        and assigns the available delivery boy without manual manager intervention.
        """
        from delivery.models import DeliveryBoyProfile, DeliveryAssignment

        # Configure shop for auto assignment
        self.shop.delivery_assignment_mode = 'auto'
        self.shop.latitude = Decimal("19.0760")
        self.shop.longitude = Decimal("72.8777")
        self.shop.save()

        # Create delivery boy user & profile
        delivery_user = User.objects.create_user(
            username="delivery_boy_auto",
            phone="9777777771",
            password="driverPassword123",
            role="delivery_boy",
            first_name="Speedy",
            last_name="Rider",
        )
        driver_profile = DeliveryBoyProfile.objects.create(
            user=delivery_user,
            shop=self.shop,
            full_name="Speedy Rider",
            phone="9777777771",
            is_online=True,
            is_available=True,
            max_active_orders=3,
            current_latitude=Decimal("19.0765"),
            current_longitude=Decimal("72.8780"),
        )

        # Create delivery order
        order = Order.objects.create(
            order_number="ORD-TEST-DELIVERY-01",
            shop=self.shop,
            customer=self.manager,
            delivery_option='delivery',
            status='preparing',
            delivery_address="456 Hill Road",
            delivery_latitude=Decimal("19.0800"),
            delivery_longitude=Decimal("72.8800"),
            total_amount=Decimal("150.00"),
        )

        # Manager or preparing staff marks the order ready
        self.client.force_authenticate(user=self.manager)
        res_ready = self.client.post(f"/api/orders/{order.id}/ready/")
        self.assertEqual(res_ready.status_code, status.HTTP_200_OK)

        # Verify parcel was created
        order.refresh_from_db()
        self.assertEqual(order.status, 'ready')
        self.assertTrue(hasattr(order, 'parcel'))
        self.assertEqual(order.parcel.status, 'assigned')

        # Verify automatic DeliveryAssignment was created
        assignment = DeliveryAssignment.objects.filter(order=order).first()
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.delivery_boy, driver_profile)
        self.assertEqual(assignment.assignment_mode, 'auto')
        self.assertEqual(assignment.status, 'assigned')

    def test_manager_cancel_online_order_shop_vs_customer_fault(self):
        """Test manager cancels online order: shop fault keeps points; customer fault deducts points and flags."""
        from accounts.models import CustomerProfile, CustomerFlag
        from orders.serializers import OrderSerializer

        # Create customer user
        customer = User.objects.create_user(
            username="online_cust_01",
            phone="9876500099",
            password="password123",
            role="customer",
        )
        profile, _ = CustomerProfile.objects.get_or_create(user=customer, defaults={"trust_score": 100})
        profile.trust_score = 100
        profile.is_flagged = False
        profile.save()

        # Order 1: Cancelled due to shop issue (e.g. item not available)
        order_shop = Order.objects.create(
            order_number="ORD-TEST-SHOP-FAULT-01",
            shop=self.shop,
            customer=customer,
            order_type="online",
            delivery_option="pickup",
            status="accepted",
            total_amount=Decimal("120.00"),
        )

        self.client.force_authenticate(user=self.manager)
        res_shop = self.client.post(
            f"/api/orders/{order_shop.id}/reject/",
            {"reason": "Item not available: Special Roti", "fault_type": "shop"},
            format="json",
        )
        self.assertEqual(res_shop.status_code, status.HTTP_200_OK)
        self.assertEqual(res_shop.data["fault_type"], "shop")
        self.assertEqual(res_shop.data["points_deducted"], 0)
        self.assertFalse(res_shop.data["customer_flagged"])

        # Customer profile must be untouched
        profile.refresh_from_db()
        self.assertEqual(profile.trust_score, 100)
        self.assertFalse(profile.is_flagged)

        # Order 2: Cancelled due to customer fault (not responding / no-show)
        order_cust = Order.objects.create(
            order_number="ORD-TEST-CUST-FAULT-02",
            shop=self.shop,
            customer=customer,
            order_type="online",
            delivery_option="pickup",
            status="ready",
            total_amount=Decimal("200.00"),
        )

        res_cust = self.client.post(
            f"/api/orders/{order_cust.id}/reject/",
            {"reason": "Customer not coming to pickup and not responding to calls", "fault_type": "customer"},
            format="json",
        )
        self.assertEqual(res_cust.status_code, status.HTTP_200_OK)
        self.assertEqual(res_cust.data["fault_type"], "customer")
        self.assertEqual(res_cust.data["points_deducted"], 15)
        self.assertTrue(res_cust.data["customer_flagged"])

        # Customer profile must now have points deducted and be flagged
        profile.refresh_from_db()
        self.assertEqual(profile.trust_score, 85)
        self.assertTrue(profile.is_flagged)

        # Verify CustomerFlag was created
        flags = CustomerFlag.objects.filter(customer=customer)
        self.assertEqual(flags.count(), 1)
        self.assertIn("Customer not coming to pickup", flags.first().reason)

        # Verify OrderSerializer outputs customer_is_flagged and customer_trust_score
        order_cust.refresh_from_db()
        serialized = OrderSerializer(order_cust).data
        self.assertTrue(serialized["customer_is_flagged"])
        self.assertEqual(serialized["customer_trust_score"], 85)
        self.assertTrue(len(serialized["customer_flag_reasons"]) > 0)


