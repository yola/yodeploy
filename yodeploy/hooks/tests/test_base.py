import unittest

from yodeploy.hooks.base import DeployHook


class TestDeployHook(unittest.TestCase):
    """Trivial tests to exercise and enforce the public API"""

    def setUp(self):
        self.dh = DeployHook('test', None, '/tmp/test', '123', {}, None)

    def test_hooks(self):
        self.dh.prepare()
        self.dh.deployed()

    def test_attributes(self):
        self.assertEqual(self.dh.app, 'test')
        self.assertEqual(self.dh.root, '/tmp/test')
        self.assertEqual(self.dh.version, '123')
        self.assertEqual(self.dh.settings, {})
        self.assertEqual(self.dh.repository, None)
        self.assertEqual(self.dh.deploy_dir, '/tmp/test/versions/123')
        self.assertEqual(self.dh.deploy_path('foo'),
                         '/tmp/test/versions/123/foo')
