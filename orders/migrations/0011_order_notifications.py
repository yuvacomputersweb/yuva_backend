# Adds the WhatsApp message log for orders. Only creates one new table.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        (
            "orders",
            "0010_order_advance_amount_order_collectible_cod_amount_order_is_partial_cod",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderNotification",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "event",
                    models.CharField(
                        choices=[
                            ("order_placed", "Order placed"),
                            ("payment_received", "Payment received"),
                            ("order_shipped", "Shipped"),
                            ("out_for_delivery", "Out for delivery"),
                            ("order_delivered", "Delivered"),
                            ("order_cancelled", "Cancelled"),
                        ],
                        max_length=30,
                    ),
                ),
                ("template", models.CharField(blank=True, max_length=100)),
                ("phone", models.CharField(blank=True, max_length=20)),
                ("success", models.BooleanField(default=False)),
                ("response", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="orders.order",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
