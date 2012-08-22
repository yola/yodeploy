import unittest
from ..django import DjangoApp


class TestDjangoHook(unittest.TestCase):

    def setUp(self):
        self.dh = DjangoApp('test', None, '/tmp/test', '123', {}, None)

    def test_vhost_attributes(self):
        self.assertEqual(self.dh.vhost_path,
            '/etc/apache2/sites-enabled')
        self.assertEqual(self.dh.vhost_snippet_path,
            '/etc/apache2/yola.d/services')
