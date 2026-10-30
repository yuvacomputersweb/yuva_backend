"""
Pull the latest Delhivery status for every open shipment.

Moves orders to Shipped / Delivered and sends the matching WhatsApp
messages (including "out for delivery"). Run it from cron, e.g. every
30 minutes:

    */30 * * * * cd /var/www/myproject/project && ../venv/bin/python manage.py sync_delhivery_status
"""
from django.core.management.base import BaseCommand

from orders.models import Order
from orders.tracking import sync_order


class Command(BaseCommand):
    help = "Sync open Delhivery shipments and notify customers on WhatsApp"

    def add_arguments(self, parser):
        parser.add_argument("--order", type=int, help="Sync a single order id")

    def handle(self, *args, **options):
        orders = Order.objects.exclude(delhivery_waybill__isnull=True).exclude(delhivery_waybill="")
        if options.get("order"):
            orders = orders.filter(pk=options["order"])
        else:
            orders = orders.exclude(order_status__in=["Delivered", "Cancelled"])

        counts = {}
        for order in orders:
            stage = sync_order(order) or "unreadable"
            counts[stage] = counts.get(stage, 0) + 1
            self.stdout.write(f"Order #{order.id} ({order.delhivery_waybill}): {stage}")
        self.stdout.write(self.style.SUCCESS(f"Synced {sum(counts.values())} shipment(s): {counts or 'none open'}"))
