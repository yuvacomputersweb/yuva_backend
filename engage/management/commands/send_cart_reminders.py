"""
One WhatsApp reminder for carts left 3+ hours without ordering.

Cron (hourly, between 10 AM and 8 PM India time = 04:30–14:30 UTC):
  30 4-14 * * * cd /var/www/myproject/project && ../venv/bin/python manage.py send_cart_reminders
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from engage.models import CartSnapshot
from engage.whatsapp import send, site_url
from orders.models import Order

WAIT = timedelta(hours=3)
GIVE_UP = timedelta(days=2)


def customer_phone(user):
    if getattr(user, 'phone', None):
        return user.phone
    address = user.saved_addresses.order_by('-is_default', '-id').first()
    if address and address.phone:
        return address.phone
    order = Order.objects.filter(user=user).exclude(phone='').order_by('-id').first()
    return order.phone if order else ''


class Command(BaseCommand):
    help = 'Send one WhatsApp reminder for each cart left without ordering.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        now = timezone.now()
        due = CartSnapshot.objects.select_related('user').filter(
            reminded_at__isnull=True, updated_at__lte=now - WAIT, updated_at__gte=now - GIVE_UP,
        )
        sent = 0
        for cart in due:
            if not cart.items:
                continue
            if Order.objects.filter(user=cart.user, created_at__gte=cart.updated_at - timedelta(minutes=5)).exists():
                cart.delete()  # they ordered — nothing to remind
                continue
            phone = customer_phone(cart.user)
            if not phone:
                continue
            first = cart.items[0]['title']
            more = len(cart.items) - 1
            params = {
                'name': (cart.user.first_name or 'there').strip(),
                'product_name': f"{first} and {more} more" if more > 0 else first,
                'cart_link': site_url('/checkout'),
            }
            if opts['dry_run']:
                self.stdout.write(f"{phone}: {params}")
                continue
            send('cart_reminder', phone, params)
            cart.reminded_at = now
            cart.save(update_fields=['reminded_at'])
            sent += 1
        self.stdout.write(self.style.SUCCESS(f'{sent} reminder(s) sent'))
