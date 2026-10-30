from unittest import mock

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from store.models import Brand, Category, Product, ProductVariant

URL = '/api/store/stock-sync/'
TOKEN = 'test-sync-token'


@override_settings(STOCK_SYNC_TOKEN=TOKEN)
class StockSyncTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        brand = Brand.objects.create(name='Dell', slug='dell')
        cat = Category.objects.create(name='Laptops', slug='laptops')
        # Per-configuration counts (like MacBooks); shared model stock is tested below.
        self.product = Product.objects.create(title='Dell Latitude 5420', sku='DELL-5420', brand=brand, category=cat,
                                              price='30000', stock_mode='variant')
        self.v1 = ProductVariant.objects.create(product=self.product, processor='Intel Core i5 11th Gen', ram='8GB', storage='256GB SSD', stock=5, price_override='0')
        self.v2 = ProductVariant.objects.create(product=self.product, processor='Intel Core i7 11th Gen', ram='16GB', storage='512GB SSD', stock=0, price_override='4000')

    def post(self, body, token=TOKEN):
        return self.client.post(URL, body, format='json', **({'HTTP_X_STOCK_SYNC_TOKEN': token} if token is not None else {}))

    def test_rejects_missing_or_wrong_token(self):
        self.assertEqual(self.post({'items': []}, token=None).status_code, 403)
        self.assertEqual(self.post({'items': []}, token='wrong').status_code, 403)

    @override_settings(STOCK_SYNC_TOKEN='')
    def test_switched_off_without_token_setting(self):
        self.assertEqual(self.post({'items': []}).status_code, 503)

    def test_updates_stock_by_id_and_by_keys(self):
        r = self.post({'items': [
            {'id': self.v1.id, 'stock': 3},
            {'product_sku': 'DELL-5420', 'processor': 'Intel Core i7 11th Gen', 'ram': '16GB', 'storage': '512GB SSD', 'stock': 2},
        ]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sorted((c['id'], c['old'], c['new']) for c in r.data['changed']),
                         sorted([(self.v1.id, 5, 3), (self.v2.id, 0, 2)]))
        self.v1.refresh_from_db(); self.v2.refresh_from_db()
        self.assertEqual((self.v1.stock, self.v2.stock), (3, 2))
        self.assertEqual(str(self.v2.price_override), '4000.00')   # only stock changes

    def test_unchanged_not_found_and_bad_rows(self):
        r = self.post({'items': [
            {'id': self.v1.id, 'stock': 5},
            {'id': 999999, 'stock': 1},
            {'product_sku': 'NOPE', 'ram': '8GB', 'storage': '256GB SSD', 'stock': 1},
            {'id': self.v2.id, 'stock': -1},
            {'id': self.v2.id, 'stock': 'abc'},
        ]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['unchanged'], 1)
        self.assertEqual(len(r.data['not_found']), 2)
        self.assertEqual(len(r.data['errors']), 2)
        self.assertEqual(r.data['changed'], [])

    def test_dry_run_changes_nothing(self):
        r = self.post({'items': [{'id': self.v1.id, 'stock': 1}], 'dry_run': True})
        self.assertEqual(r.data['changed'][0]['new'], 1)
        self.v1.refresh_from_db()
        self.assertEqual(self.v1.stock, 5)

    def test_saves_through_signals(self):
        # stock is saved with save(update_fields=['stock']) so the engage signals run
        with mock.patch.object(ProductVariant, 'save', autospec=True, side_effect=ProductVariant.save) as save:
            self.post({'items': [{'id': self.v2.id, 'stock': 4}]})
        save.assert_called_once()
        self.assertEqual(save.call_args.kwargs.get('update_fields'), ['stock'])

    def test_back_in_stock_and_low_stock_messages_are_queued(self):
        with mock.patch('engage.signals.notify_back_in_stock') as back, \
             mock.patch('engage.signals.alert_owner') as low, \
             self.captureOnCommitCallbacks(execute=True):
            self.post({'items': [{'id': self.v2.id, 'stock': 3},    # 0 -> 3: back in stock
                                 {'id': self.v1.id, 'stock': 1}]})  # 5 -> 1: low stock
        back.assert_called_once()
        low.assert_called_once()


@override_settings(STOCK_SYNC_TOKEN=TOKEN)
class StockSyncOrdersTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from orders.models import Order, OrderItem
        self.client = APIClient()
        user = get_user_model().objects.create_user(email='c@example.com', password='x')
        brand = Brand.objects.create(name='Dell', slug='dell')
        cat = Category.objects.create(name='Laptops', slug='laptops')
        product = Product.objects.create(title='Dell Latitude 5420', sku='DELL-5420', brand=brand, category=cat, price='30000')
        self.v = ProductVariant.objects.create(product=product, processor='Intel Core i5 11th Gen', ram='8GB', storage='256GB SSD', stock=5)
        def order(pay, st):
            o = Order.objects.create(user=user, first_name='Ravi', phone='9876543210', city='Hyderabad', shipping_address='x',
                                     total_amount='30000', payment_status=pay, order_status=st)
            OrderItem.objects.create(order=o, product=product, variant=self.v, product_name='Dell Latitude 5420',
                                     variant_label='i5/8/256', price='30000', quantity=1, serial_number='DZKNHW3')
            return o
        self.paid = order('Paid', 'Processing')
        self.unpaid = order('Pending', 'Pending')
        self.cancelled = order('Paid', 'Cancelled')

    def get(self, q='', token=TOKEN):
        return self.client.get('/api/store/stock-sync/orders/' + q, **({'HTTP_X_STOCK_SYNC_TOKEN': token} if token else {}))

    def test_needs_token(self):
        self.assertEqual(self.get(token=None).status_code, 403)

    def test_lists_paid_and_cancelled_only(self):
        r = self.get()
        self.assertEqual(r.status_code, 200)
        ids = [o['id'] for o in r.data['orders']]
        self.assertEqual(sorted(ids), sorted([self.paid.id, self.cancelled.id]))
        item = r.data['orders'][0]['items'][0]
        self.assertEqual((item['variant_id'], item['product_sku'], item['quantity'], item['serial_number']),
                         (self.v.id, 'DELL-5420', 1, 'DZKNHW3'))

    def test_since_returns_only_newer_changes(self):
        first = self.get().data
        r = self.get('?since=' + first['next_since'].replace('+', '%2B'))
        self.assertEqual(r.data['orders'], [])
        self.paid.order_status = 'Cancelled'; self.paid.save()
        r = self.get('?since=' + first['next_since'].replace('+', '%2B'))
        self.assertEqual([o['id'] for o in r.data['orders']], [self.paid.id])

    def test_bad_since(self):
        self.assertEqual(self.get('?since=yesterday').status_code, 400)


@override_settings(STOCK_SYNC_TOKEN=TOKEN)
class StockSyncSafetyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        brand = Brand.objects.create(name='HP', slug='hp')
        cat = Category.objects.create(name='Laptops 2', slug='laptops-2')
        self.product = Product.objects.create(title='HP 840 G6', sku='HP-840', brand=brand, category=cat, price='25000',
                                              stock_mode='variant')
        self.variants = [ProductVariant.objects.create(product=self.product, processor=f'P{i}', ram='8GB',
                                                       storage='256GB SSD', stock=2, price_override='0') for i in range(6)]

    def post(self, body):
        return self.client.post(URL, body, format='json', HTTP_X_STOCK_SYNC_TOKEN=TOKEN)

    def test_refuses_a_sync_that_sells_out_most_of_the_shop(self):
        body = {'items': [{'id': v.id, 'stock': 0} for v in self.variants]}
        r = self.post(body)
        self.assertEqual(r.status_code, 409)
        self.assertFalse(ProductVariant.objects.filter(stock=0).exists())   # nothing saved
        r = self.post({**body, 'force': True})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ProductVariant.objects.filter(stock=0).count(), 6)

    def test_a_few_sell_outs_are_fine(self):
        r = self.post({'items': [{'id': v.id, 'stock': 0} for v in self.variants[:2]]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['changed']), 2)

    def test_dry_run_string_false_saves_and_duplicates_are_reported(self):
        v = self.variants[0]
        r = self.post({'items': [{'id': v.id, 'stock': 3}, {'id': v.id, 'stock': 9}], 'dry_run': 'false'})
        self.assertFalse(r.data['dry_run'])
        v.refresh_from_db()
        self.assertEqual(v.stock, 3)
        self.assertIn('already set', r.data['errors'][0]['error'])



@override_settings(STOCK_SYNC_TOKEN=TOKEN)
class ModelStockTests(TestCase):
    """Windows laptops: one count per model; RAM/SSD options all sell from it."""

    def setUp(self):
        self.client = APIClient()
        brand = Brand.objects.create(name='Lenovo', slug='lenovo')
        cat = Category.objects.create(name='Laptops 3', slug='laptops-3')
        self.product = Product.objects.create(title='ThinkPad T480', sku='T480', brand=brand, category=cat,
                                              price='22000', stock=3)
        self.base = ProductVariant.objects.create(product=self.product, ram='8GB', storage='256GB SSD', stock=0, price_override='0')
        self.up = ProductVariant.objects.create(product=self.product, ram='16GB', storage='512GB SSD', stock=0, price_override='7500')

    def post(self, body):
        return self.client.post(URL, body, format='json', HTTP_X_STOCK_SYNC_TOKEN=TOKEN)

    def test_every_configuration_shows_the_model_count(self):
        data = self.client.get(f'/api/store/products/{self.product.slug}/').data
        self.assertEqual(sorted(v['stock'] for v in data['variants']), [3, 3])
        self.assertEqual((data['stock'], data['in_stock'], data['stock_mode']), (3, True, 'model'))

    def test_two_configurations_in_one_order_both_count(self):
        # each order line loads its own copy of the product; both sales must stick
        a = ProductVariant.objects.select_related('product').get(pk=self.base.pk)
        b = ProductVariant.objects.select_related('product').get(pk=self.up.pk)
        self.assertTrue(a.take_stock(1))
        self.assertTrue(b.take_stock(1))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)

    def test_selling_any_configuration_uses_the_shared_count(self):
        self.assertTrue(self.up.take_stock(2))
        self.product.refresh_from_db(); self.base.refresh_from_db()
        self.assertEqual(self.product.stock, 1)
        self.assertEqual(self.base.available, 1)
        self.assertFalse(self.base.take_stock(2))      # only 1 left
        self.base.return_stock(1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)

    def test_sync_sets_the_model_count_by_sku(self):
        r = self.post({'items': [{'product_sku': 'T480', 'stock': 7}]})
        self.assertEqual(r.data['changed'], [{'level': 'model', 'id': None, 'product_sku': 'T480', 'old': 3, 'new': 7}])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_a_configuration_row_sets_the_model_count_once(self):
        r = self.post({'items': [{'id': self.up.id, 'stock': 2}, {'id': self.base.id, 'stock': 9}]})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 2)
        self.assertIn('already set', r.data['errors'][0]['error'])

    def test_sku_only_row_for_a_per_configuration_product_is_refused(self):
        self.product.stock_mode = 'variant'; self.product.save()
        r = self.post({'items': [{'product_sku': 'T480', 'stock': 2}]})
        self.assertIn('per configuration', r.data['errors'][0]['error'])

    def test_alerts_follow_the_model_count(self):
        from unittest import mock
        self.product.stock = 0; self.product.save()
        with mock.patch('engage.signals.notify_back_in_stock') as back, \
             mock.patch('engage.signals.alert_owner') as low, \
             self.captureOnCommitCallbacks(execute=True):
            self.post({'items': [{'product_sku': 'T480', 'stock': 4}]})      # 0 -> 4: back in stock
            self.up.take_stock(3)                                            # 4 -> 1: low stock
        back.assert_called_once()
        low.assert_called_once()
        # a configuration row's own counter no longer triggers anything
        with mock.patch('engage.signals.notify_back_in_stock') as back2, self.captureOnCommitCallbacks(execute=True):
            self.base.stock = 5; self.base.save()
        back2.assert_not_called()
