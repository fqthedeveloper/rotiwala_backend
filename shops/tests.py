from django.test import TestCase
from datetime import datetime, timedelta, time
from django.utils import timezone

from accounts.models import User
from orders.models import Order
from .models import Shop, ShopOrderCapacityAudit
from .services import (
	ensure_online_order_capacity,
	OnlineOrderingUnavailable,
	get_business_date,
	get_order_capacity_snapshot,
)


class OrderCapacityServiceTests(TestCase):
	def setUp(self):
		self.shop = Shop.objects.create(
			name="Test Roti Waale", phone="9999999999", address="Test address",
			max_online_orders=2,
		)
		self.customer = User.objects.create_user(
			username="customer", phone="9999999998", password="password", role="customer",
		)

	def create_order(self, status="pending", order_type="online", pickup_time=None):
		return Order.objects.create(
			order_number=f"TEST-{Order.objects.count() + 1}",
			customer=self.customer,
			shop=self.shop,
			order_type=order_type,
			status=status,
			pickup_type="scheduled" if pickup_time else "instant",
			pickup_time=pickup_time,
		)

	def test_order_allowed_below_capacity(self):
		self.create_order()
		self.assertTrue(get_order_capacity_snapshot(self.shop)["accepting_online_orders"])
		self.assertEqual(get_order_capacity_snapshot(self.shop)["available_capacity"], 1)

	def test_scheduled_order_counts_on_pickup_date(self):
		future_date = get_business_date() + timedelta(days=2)
		future_pickup = timezone.make_aware(
			datetime.combine(future_date, time(12))
		)
		self.create_order(pickup_time=future_pickup)
		self.assertEqual(get_order_capacity_snapshot(self.shop)["active_online_orders"], 0)
		self.assertEqual(
			get_order_capacity_snapshot(self.shop, future_date)["active_online_orders"],
			1,
		)

	def test_order_rejected_at_capacity(self):
		self.create_order()
		self.create_order()
		with self.assertRaises(OnlineOrderingUnavailable) as context:
			ensure_online_order_capacity(self.shop)
		self.assertEqual(context.exception.code, "ONLINE_ORDER_CAPACITY_REACHED")

	def test_completed_order_releases_capacity(self):
		order = self.create_order()
		self.create_order()
		order.status = "collected"
		order.save(update_fields=["status"])
		self.assertTrue(get_order_capacity_snapshot(self.shop)["accepting_online_orders"])

	def test_rejected_and_cancelled_orders_do_not_consume_capacity(self):
		self.create_order(status="rejected")
		self.create_order(status="cancelled")
		snapshot = get_order_capacity_snapshot(self.shop)
		self.assertEqual(snapshot["active_online_orders"], 0)
		self.assertTrue(snapshot["accepting_online_orders"])

	def test_manual_pause_is_separate_from_capacity(self):
		self.shop.online_orders_manually_paused = True
		self.shop.save(update_fields=["online_orders_manually_paused"])
		with self.assertRaises(OnlineOrderingUnavailable) as context:
			ensure_online_order_capacity(self.shop)
		self.assertEqual(context.exception.code, "ONLINE_ORDERING_PAUSED")

	def test_resuming_manual_pause_allows_orders_when_capacity_exists(self):
		self.shop.online_orders_manually_paused = True
		self.shop.save(update_fields=["online_orders_manually_paused"])
		self.shop.online_orders_manually_paused = False
		self.shop.save(update_fields=["online_orders_manually_paused"])
		self.assertTrue(get_order_capacity_snapshot(self.shop)["accepting_online_orders"])

	def test_walk_in_orders_do_not_consume_online_capacity(self):
		self.create_order(order_type="walkin")
		self.assertEqual(get_order_capacity_snapshot(self.shop)["active_online_orders"], 0)

	def test_lowering_capacity_does_not_change_existing_orders(self):
		self.create_order()
		self.create_order()
		self.shop.max_online_orders = 1
		self.shop.save(update_fields=["max_online_orders"])
		self.assertEqual(Order.objects.filter(shop=self.shop).count(), 2)
		self.assertFalse(get_order_capacity_snapshot(self.shop)["accepting_online_orders"])

	def test_increasing_capacity_reopens_full_shop(self):
		self.create_order()
		self.create_order()
		self.shop.max_online_orders = 3
		self.shop.save(update_fields=["max_online_orders"])
		self.assertTrue(get_order_capacity_snapshot(self.shop)["accepting_online_orders"])

	def test_capacity_audit_model_is_available(self):
		ShopOrderCapacityAudit.objects.create(
			shop=self.shop, action="capacity_changed", old_value="2", new_value="3",
		)
		self.assertEqual(self.shop.order_capacity_audits.count(), 1)
