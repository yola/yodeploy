import os

from yoconfigurator.tests import unittest

from yodeploy.tests.samples.helpers import build_sample, clear, deploy_sample


class TestConfiguredAppWithConfigTemplate(unittest.TestCase):

    def setUp(self):
        clear('config-template')
        build_sample('configs')
        build_sample('config-template')
        deploy_sample('config-template')
        self.deployed_app = os.path.join(
            os.path.dirname(__file__),
            'filesys', 'deployed', 'config-template', 'live')

    def test_has_config_in_deployed_source(self):
        deployed_config = os.path.join(self.deployed_app, 'src', 'config.js')
        self.assertTrue(os.path.exists(deployed_config))

    def test_has_a_config_with_expected_js(self):
        with open(os.path.join(self.deployed_app, 'src', 'config.js')) as f:
            content = f.read().strip()
        expected = 'window.CONFIGURATION = {"conftpl": {"msg": "hi!"}};'
        self.assertEquals(expected, content)
