"""
Confirm orders that Razorpay was paid for but the website never heard about
(customer closed the page, webhook missed). Safe to run any time.

Cron (every 15 minutes):
  */15 * * * * cd /var/www/myproject/project && ../venv/bin/python manage.py check_pending_payments >> $HOME/payments.log 2>&1
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from orders.models import Order
from payments.confirm import confirm_paid_order
from payments.razorpay_client import _get_client


class Command(BaseCommand):
    help = 'Ask Razorpay about recent unpaid orders and confirm the ones that were actually paid.'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=72, help='How far back to look (default 72).')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, hours, dry_run, **opts):
        now = timezone.now()
        orders = Order.objects.filter(
            payment_status__in=['Pending', 'Failed'],
            razorpay_order_id__isnull=False,
            created_at__gte=now - timedelta(hours=hours),
            created_at__lte=now - timedelta(minutes=5),   # give the normal flow time to finish
        ).exclude(razorpay_order_id='').exclude(order_status='Cancelled')
        client = _get_client()
        confirmed = 0
        for order in orders:
            try:
                payments = client.order.payments(order.razorpay_order_id).get('items', [])
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f"Order #{order.id}: Razorpay lookup failed: {exc}")
                continue
            captured = next((p for p in payments if p.get('status') == 'captured'), None)
            if not captured:
                continue
            if dry_run:
                self.stdout.write(f"Order #{order.id} was paid ({captured['id']}) — would confirm")
                continue
            if confirm_paid_order(order, captured['id']):
                confirmed += 1
                self.stdout.write(f"Order #{order.id} confirmed from Razorpay payment {captured['id']}")
        self.stdout.write(self.style.SUCCESS(f"Checked {orders.count()} unpaid order(s), confirmed {confirmed}."))
