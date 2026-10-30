"""
Evening WhatsApp summary to the shop owner.

Cron (8:30 PM India time = 15:00 UTC):
  0 15 * * * cd /var/www/myproject/project && ../venv/bin/python manage.py send_daily_summary
"""
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from engage.whatsapp import alert_owner
from orders.models import Order, ReturnRequest

IST = ZoneInfo('Asia/Kolkata')


class Command(BaseCommand):
    help = "Send today's orders / payments / shipping summary to the owner on WhatsApp."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Print instead of sending.')

    def handle(self, *args, **opts):
        now = timezone.now().astimezone(IST)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today = Order.objects.filter(created_at__gte=start, created_at__lt=start + timedelta(days=1))
        paid = today.filter(payment_status__in=['Paid', 'Deposit Paid'])
        revenue = paid.aggregate(s=Sum('total_amount'))['s'] or 0
        to_ship = Order.objects.filter(order_status__in=['Processing', 'Confirmed']).count()
        returns = ReturnRequest.objects.filter(status='Pending').count()

        params = {
            'date': now.strftime('%d %b %Y'),
            'new_orders': f"{today.count()} ({paid.count()} paid)",
            'revenue': f"Rs. {float(revenue):,.0f}",
            'to_ship': str(to_ship),
            'pending_returns': str(returns),
        }
        if opts['dry_run']:
            self.stdout.write(str(params))
            return
        alert_owner('daily_summary', params)
        self.stdout.write(self.style.SUCCESS(f"Summary sent: {params}"))
