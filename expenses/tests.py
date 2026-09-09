from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from expenses.models import (
    ExpenseCategory,
    ExpenseMasterItem,
    MaintenanceExpense,
    RawMaterialExpense,
    Vendor,
)
from expenses.serializers import RawMaterialExpenseSerializer
from shops.models import Shop


class MaintenanceExpenseCreateTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.shop = Shop.objects.create(
            name="Test Shop",
            phone="1234567890",
            address="Test address",
        )
        self.user = User.objects.create_user(
            username="superadmin",
            phone="1111111111",
            password="testpass123",
            role="super_admin",
        )
        self.client.force_authenticate(self.user)

    def test_super_admin_can_create_maintenance_with_shop_id(self):
        url = reverse("create-maintenance")
        payload = {
            "title": "AC Repair",
            "description": "Repair the air conditioner",
            "amount": "150.00",
            "maintenance_date": "2026-07-29",
            "shop_id": self.shop.id,
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(MaintenanceExpense.objects.count(), 1)
        self.assertEqual(MaintenanceExpense.objects.first().shop, self.shop)
        self.assertEqual(MaintenanceExpense.objects.first().created_by, self.user)


class ExpensePaymentFieldRegressionTests(TestCase):
    def test_payment_fields_are_persisted_and_serialized_for_expenses(self):
        shop = Shop.objects.create(name="Payment Shop", phone="2222222222", address="Address")
        user = User.objects.create_user(
            username="paymentadmin",
            phone="2222222222",
            password="testpass123",
            role="super_admin",
        )
        category = ExpenseCategory.objects.create(name="Raw Materials")
        item = ExpenseMasterItem.objects.create(category=category, name="Atta")

        maintenance = MaintenanceExpense.objects.create(
            shop=shop,
            title="AC Service",
            description="Annual check",
            amount=Decimal("150.00"),
            maintenance_date="2026-07-29",
            created_by=user,
            payment_method="UPI",
            utr_number="UTR123456789",
        )

        self.assertEqual(maintenance.payment_method, "UPI")
        self.assertEqual(maintenance.utr_number, "UTR123456789")

        vendor = Vendor.objects.create(shop=shop, name="Vendor A")
        raw_material = RawMaterialExpense.objects.create(
            shop=shop,
            vendor=vendor,
            item=item,
            custom_item_name="",
            quantity=Decimal("10"),
            unit="KG",
            unit_price=Decimal("50.00"),
            amount=Decimal("500.00"),
            note="",
            expense_date="2026-07-29",
            created_by=user,
            payment_method="CASH",
            utr_number="",
        )

        self.assertEqual(raw_material.payment_method, "CASH")
        self.assertEqual(raw_material.utr_number, "")

        payload = RawMaterialExpenseSerializer(raw_material).data
        self.assertEqual(payload["payment_method"], "CASH")
        self.assertEqual(payload["utr_number"], "")
