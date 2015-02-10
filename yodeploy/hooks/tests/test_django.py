import unittest
from yodeploy.hooks.django import DjangoApp


class TestDjangoHook(unittest.TestCase):

    def setUp(self):
        self.dh = DjangoApp('test', None, '/tmp/test', '123', {}, None)

    def test_vhost_attributes(self):
        self.assertEqual(self.dh.vhost_path, '/etc/apache2/sites-enabled')
