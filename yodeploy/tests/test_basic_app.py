import os

from yoconfigurator.tests import unittest

from yodeploy.tests.samples.helpers import build_sample, clear, deploy_sample


class TestBasicAppDeploy(unittest.TestCase):

    def setUp(self):
        clear('basic_app')
        build_sample('basic_app')
        deploy_sample('basic_app')
        self.deployed_app = os.path.join(
            os.path.dirname(__file__),
            'filesys', 'deployed', 'basic_app', 'live')

    def test_hello_world_is_deployed(self):
        deployed_file = os.path.join(self.deployed_app, 'hello_world.txt')
        self.assertTrue(os.path.exists(deployed_file))
