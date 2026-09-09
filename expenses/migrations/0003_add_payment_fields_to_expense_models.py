from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("expenses", "0002_alter_expenseentry_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name='maintenanceexpense',
            name='payment_method',
            field=models.CharField(choices=[('CASH', 'Cash'), ('UPI', 'UPI')], default='CASH', max_length=16),
        ),
        migrations.AddField(
            model_name='maintenanceexpense',
            name='utr_number',
            field=models.CharField(blank=True, default='', max_length=80, null=True),
        ),
        migrations.AddField(
            model_name='rawmaterialexpense',
            name='payment_method',
            field=models.CharField(choices=[('CASH', 'Cash'), ('UPI', 'UPI')], default='CASH', max_length=16),
        ),
        migrations.AddField(
            model_name='rawmaterialexpense',
            name='utr_number',
            field=models.CharField(blank=True, default='', max_length=80, null=True),
        ),
    ]
