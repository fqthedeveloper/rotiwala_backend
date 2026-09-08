from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("shops", "0007_rename_shops_shop_id_5a7f13_idx_shops_shopo_shop_id_930b0f_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="shop",
            name="delivery_fee",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Delivery fee charged below the free-delivery threshold",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="shop",
            name="free_delivery_min_order",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Minimum discounted subtotal required for free delivery; zero means always free",
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name="shop",
            name="minimum_delivery_order",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Minimum discounted subtotal required to select delivery",
                max_digits=10,
            ),
        ),
    ]