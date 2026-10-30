import json
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from orders.models import Order, OrderItem
from store.models import Brand, Category, Product, ProductVariant


class MissedPaymentTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name='Dell', slug='dell-p')
        cat = Category.objects.create(name='Laptops P', slug='laptops-p')
        self.product = Product.objects.create(title='Latitude 5420', sku='L5420', brand=brand, category=cat,
                                              price='31500', stock=3)
        self.variant = ProductVariant.objects.create(product=self.product, ram='8GB', storage='256GB SSD', stock=0, price_override='0')
        self.user = get_user_model().objects.create_superuser(email='admin@x.in', password='x')
        self.order = Order.objects.create(
            user=self.user, first_name='Amit', phone='9700000000', total_amount='31500', shipping_address='x',
            payment_method='COD', is_partial_cod=True, advance_amount='389.40', collectible_cod_amount='31500',
            payment_status='Pending', order_status='Pending', razorpay_order_id='order_TEST1',
        )
        OrderItem.objects.create(order=self.order, product=self.product, variant=self.variant,
                                 product_name='Latitude 5420', price='31500', quantity=1)
        self.created_ago(minutes=30)

    def created_ago(self, **delta):
        Order.objects.filter(pk=self.order.pk).update(created_at=timezone.now() - timedelta(**delta))

    def assert_confirmed(self, logistics):
        self.order.refresh_from_db(); self.product.refresh_from_db()
        self.assertEqual(self.order.payment_status, 'Deposit Paid')
        self.assertEqual(self.order.order_status, 'Processing')
        self.assertEqual(self.product.stock, 2)
        logistics.assert_called_once()

    @override_settings(RAZORPAY_WEBHOOK_SECRET='whsec', RAZORPAY_KEY_ID='k', RAZORPAY_KEY_SECRET='s')
    def test_webhook_confirms_once(self):
        body = {'event': 'payment.captured',
                'payload': {'payment': {'entity': {'order_id': 'order_TEST1', 'id': 'pay_ABC'}}}}
        with mock.patch('payments.views._get_client') as client, \
             mock.patch('orders.services.process_order_logistics_and_notification') as logistics:
            client.return_value.utility.verify_webhook_signature.return_value = True
            for _ in range(2):   # Razorpay may retry
                r = APIClient().post('/api/payments/webhook/', json.dumps(body), content_type='application/json',
                                     HTTP_X_RAZORPAY_SIGNATURE='sig')
                self.assertEqual(r.status_code, 200)
        self.assert_confirmed(logistics)
        self.assertEqual(self.order.razorpay_payment_id, 'pay_ABC')

    def test_admin_marking_paid_does_what_a_payment_does(self):
        from types import SimpleNamespace
        from django.contrib import admin as dj_admin
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory
        from orders.admin import OrderAdmin

        request = RequestFactory().post('/')
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        form = SimpleNamespace(changed_data=['payment_status'], initial={'payment_status': 'Pending'})
        self.order.payment_status = 'Deposit Paid'
        with mock.patch('orders.services.process_order_logistics_and_notification') as logistics:
            OrderAdmin(Order, dj_admin.site).save_model(request, self.order, form, change=True)
        self.assert_confirmed(logistics)

    @override_settings(RAZORPAY_KEY_ID='k', RAZORPAY_KEY_SECRET='s')
    def test_check_pending_payments_confirms_paid_orders_only(self):
        other = Order.objects.create(user=self.user, total_amount='100', shipping_address='x', payment_status='Pending',
                                     razorpay_order_id='order_UNPAID')
        Order.objects.filter(pk=other.pk).update(created_at=timezone.now() - timedelta(minutes=30))
        def payments(order_id):
            return {'items': [{'id': 'pay_X', 'status': 'captured'}]} if order_id == 'order_TEST1' else {'items': [{'status': 'failed'}]}
        with mock.patch('payments.management.commands.check_pending_payments._get_client') as client, \
             mock.patch('orders.services.process_order_logistics_and_notification') as logistics:
            client.return_value.order.payments.side_effect = payments
            call_command('check_pending_payments')
            call_command('check_pending_payments')   # second run: nothing left to do
        self.assert_confirmed(logistics)
        other.refresh_from_db()
        self.assertEqual(other.payment_status, 'Pending')
