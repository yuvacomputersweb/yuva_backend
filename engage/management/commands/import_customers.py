"""
Import past customers from the sales register Excel.

  python manage.py import_customers /path/to/Yuva_Sales_CRM.xlsx
"""
from django.core.management.base import BaseCommand, CommandError

from engage.customer_import import import_sales_register


class Command(BaseCommand):
    help = 'Import past sales (customers, purchase dates) from the sales register Excel file.'

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--store', default='Dilsukhnagar HQ', help='Store name when the row has none.')

    def handle(self, path, store, **opts):
        try:
            stats = import_sales_register(path, default_store=store)
        except (OSError, ValueError, KeyError) as exc:
            raise CommandError(str(exc))
        self.stdout.write(self.style.SUCCESS(
            f"Imported/updated {stats['imported']} of {stats['rows']} rows. "
            f"Skipped: {stats['skipped_no_phone']} without a valid mobile, {stats['skipped_no_date']} without a date."
        ))
