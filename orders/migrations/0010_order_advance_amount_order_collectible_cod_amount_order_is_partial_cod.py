# orders/migrations/0010_order_advance_amount_order_collectible_cod_amount_order_is_partial_cod.py
# Run: python manage.py migrate

from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        # ← matches your last migration file in orders/migrations/
        ('orders', '0009_alter_order_delhivery_waybill_and_more'),
    ]

    operations = [
        # 1. Add advance_amount
        migrations.AddField(
            model_name='order',
            name='advance_amount',
            field=models.DecimalField(
                max_digits=10, decimal_places=2,
                default=Decimal('0.00'),
                help_text="2% of total_amount paid online via Razorpay at checkout (COD orders only)"
            ),
        ),
        # 2. Add collectible_cod_amount
        migrations.AddField(
            model_name='order',
            name='collectible_cod_amount',
            field=models.DecimalField(
                max_digits=10, decimal_places=2,
                default=Decimal('0.00'),
                help_text="Amount collected on delivery = total_amount - advance_amount (COD orders only)"
            ),
        ),
        # 3. Add is_partial_cod flag
        migrations.AddField(
            model_name='order',
            name='is_partial_cod',
            field=models.BooleanField(
                default=False,
                help_text="True for COD orders that require 2% upfront deposit"
            ),
        ),
        # 4. Add 'Deposit Paid' to payment_status choices
        # Django CharField choices are validated at the form/serializer level only.
        # The DB column is just a VARCHAR — no schema change needed for adding a choice.
        # However, we alter the field to update Django's internal choices metadata.
        migrations.AlterField(
            model_name='order',
            name='payment_status',
            field=models.CharField(
                max_length=20,
                choices=[
                    ('Pending', 'Pending'),
                    ('Deposit Paid', 'Deposit Paid'),
                    ('Paid', 'Paid'),
                    ('Failed', 'Failed'),
                    ('Refunded', 'Refunded'),
                    ('Refund Pending', 'Refund Pending'),
                ],
                default='Pending',
            ),
        ),
        # 5. Zero out cod_fee — the surcharge model is retired.
        # Existing orders keep their old cod_fee value for audit purposes.
        # New orders will always receive cod_fee=0.
        # No schema change needed — it's already DecimalField with default=0.
    ]