import tempfile
import xml.etree.ElementTree as ET
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from rest_framework.test import APIClient

from orders.models import Order, OrderItem
from store.models import Brand, Category, Product, ProductImage

G = '{http://base.google.com/ns/1.0}'


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(), SITE_URL='https://www.yuvacomputers.in')
class MarketingTests(TestCase):
    def setUp(self):
        brand = Brand.objects.create(name='Dell', slug='dell-m')
        cat = Category.objects.create(name='Premium Laptops', slug='premium-m')
        self.product = Product.objects.create(title='Dell Latitude 5440 i5', sku='YC-LT-042', brand=brand,
                                              category=cat, price='48500', original_price='60000', stock=2,
                                              description='<p>Business laptop</p>')
        ProductImage.objects.create(product=self.product, is_primary=True,
                                    image=SimpleUploadedFile('a.jpg', b'\xff\xd8\xff', content_type='image/jpeg'))
        Product.objects.create(title='No photo yet', sku='YC-LT-099', brand=brand, category=cat, price='20000', stock=1)
        self.user = get_user_model().objects.create_user(email='amit@x.in', password='x')

    def test_product_feed(self):
        r = APIClient().get('/api/store/feeds/products.xml')
        self.assertEqual(r.status_code, 200)
        root = ET.fromstring(r.content)
        items = root.findall('./channel/item')
        self.assertEqual(len(items), 1)                      # the one without a photo is left out
        item = items[0]
        self.assertEqual(item.find(f'{G}id').text, 'YC-LT-042')
        self.assertEqual(item.find(f'{G}condition').text, 'refurbished')
        self.assertEqual(item.find(f'{G}availability').text, 'in_stock')
        self.assertEqual(item.find(f'{G}price').text, '60000.00 INR')
        self.assertEqual(item.find(f'{G}sale_price').text, '48500.00 INR')
        self.assertEqual(item.find(f'{G}google_product_category').text, 'Electronics > Computers > Laptops')
        self.assertTrue(item.find(f'{G}image_link').text.startswith('http'))
        self.assertEqual(item.find('link').text, f'https://www.yuvacomputers.in/product/{self.product.slug}')
        self.assertIn('1 left out', root.find('./channel/description').text)

    def _order(self):
        order = Order.objects.create(user=self.user, first_name='Amit', last_name='K', phone='+91 97008 36112',
                                     email='Amit@X.in', city='Hyderabad', state='Telangana', zip_code='500060',
                                     total_amount='48500', shipping_address='x', payment_status='Deposit Paid',
                                     tracking={'ip': '1.2.3.4', 'ua': 'Mozilla', 'fbp': 'fb.1.1.1', 'fbc': ''})
        OrderItem.objects.create(order=order, product=self.product, product_name=self.product.title, price='48500', quantity=1)
        return order

    def test_checkout_captures_browser_details(self):
        from orders.views import _checkout_tracking
        req = RequestFactory().post('/', HTTP_USER_AGENT='Mozilla/5.0', HTTP_X_FORWARDED_FOR='9.9.9.9, 10.0.0.1')
        req.data = {'tracking': {'fbp': 'fb.1.123.456', 'fbc': 'fb.1.123.abc'}}
        t = _checkout_tracking(req)
        self.assertEqual((t['ip'], t['ua'], t['fbp'], t['fbc']), ('9.9.9.9', 'Mozilla/5.0', 'fb.1.123.456', 'fb.1.123.abc'))

    @override_settings(META_PIXEL_ID='123', META_CAPI_TOKEN='tok')
    def test_meta_purchase_sent_once_with_hashed_details(self):
        import hashlib
        from orders.meta_capi import send_purchase
        order = self._order()
        with mock.patch('orders.meta_capi.requests.post') as post:
            post.return_value.status_code = 200
            self.assertTrue(send_purchase(order))
            self.assertFalse(send_purchase(order))           # never twice
        post.assert_called_once()
        event = post.call_args.kwargs['json']['data'][0]
        self.assertEqual(event['event_id'], f'order_{order.id}')     # same id as the browser pixel
        self.assertEqual(event['custom_data']['value'], 48500.0)
        self.assertEqual(event['custom_data']['content_ids'], ['YC-LT-042'])
        self.assertEqual(event['user_data']['ph'], [hashlib.sha256(b'919700836112').hexdigest()])
        self.assertEqual(event['user_data']['em'], [hashlib.sha256(b'amit@x.in').hexdigest()])
        self.assertEqual(event['user_data']['client_ip_address'], '1.2.3.4')
        self.assertNotIn('fbc', event['user_data'])
        order.refresh_from_db()
        self.assertTrue(order.tracking['meta_purchase_sent'])

    @override_settings(META_CAPI_TOKEN='')
    def test_meta_purchase_off_without_token(self):
        from orders.meta_capi import send_purchase
        with mock.patch('orders.meta_capi.requests.post') as post:
            self.assertFalse(send_purchase(self._order()))
        post.assert_not_called()

    @override_settings(META_PIXEL_ID='123', META_CAPI_TOKEN='tok', DELHIVERY_API_TOKEN='', WA_ACCESS_TOKEN='')
    def test_confirmed_orders_report_the_purchase(self):
        from orders.services import process_order_logistics_and_notification
        order = self._order()
        with mock.patch('orders.meta_capi.requests.post') as post:
            post.return_value.status_code = 200
            process_order_logistics_and_notification(order)
        self.assertEqual(post.call_count, 1)
