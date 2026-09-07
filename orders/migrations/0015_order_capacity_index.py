from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0014_walkincart_business_date_walkincart_token_number"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["shop", "order_type", "status"], name="orders_shop_id_8d5e4e_idx"),
        ),
    ]
