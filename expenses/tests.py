from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from expenses.models import MaintenanceExpense
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
