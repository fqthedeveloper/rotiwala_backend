from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("shops", "0005_shop_delivery_assignment_mode_shop_delivery_enabled_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="shop",
            name="max_online_orders",
            field=models.PositiveIntegerField(default=100),
        ),
        migrations.AddField(
            model_name="shop",
            name="online_orders_manually_paused",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="shop",
            name="manual_pause_reason",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="shop",
            name="paused_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="ShopOrderCapacityAudit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=40)),
                ("old_value", models.CharField(blank=True, max_length=255)),
                ("new_value", models.CharField(blank=True, max_length=255)),
                ("reason", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("manager", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="order_capacity_audits", to=settings.AUTH_USER_MODEL)),
                ("shop", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="order_capacity_audits", to="shops.shop")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["shop", "created_at"], name="shops_shop_id_5a7f13_idx")],
            },
        ),
    ]
