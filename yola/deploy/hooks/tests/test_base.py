import unittest

from ..base import DeployHook


class TestDeployHook(unittest.TestCase):
    """Trivial tests to exercise and enforce the public API"""

    def setUp(self):
        self.dh = DeployHook('test', None, '/tmp/test', '123', {}, None)

    def test_hooks(self):
        self.dh.prepare()
        self.dh.deployed()

    def test_app(self):
        self.assertEqual(self.dh.app, 'test')

    def test_root(self):
        self.assertEqual(self.dh.root, '/tmp/test')

    def test_version(self):
        self.assertEqual(self.dh.version, '123')

    def test_settings(self):
        self.assertEqual(self.dh.settings, {})

    def test_artifacts_factory(self):
        self.assertEqual(self.dh.artifacts_factory, None)

    def test_deploy_dir(self):
        self.assertEqual(self.dh.deploy_dir, '/tmp/test/versions/123')

    def test_deploy_path(self):
        self.assertEqual(self.dh.deploy_path('foo'),
                         '/tmp/test/versions/123/foo')
