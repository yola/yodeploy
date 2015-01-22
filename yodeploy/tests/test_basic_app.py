import os

from yoconfigurator.tests import unittest

from yodeploy.tests.samples.helpers import build_sample, clear, deploy_sample


class TestBasicAppDeploy(unittest.TestCase):

    def setUp(self):
        clear('basic-app')
        build_sample('basic-app')
        deploy_sample('basic-app')
        self.deployed_app = os.path.join(
            os.path.dirname(__file__),
            'filesys', 'deployed', 'basic-app', 'live')

    def test_is_deployable(self):
        deployed_file = os.path.join(self.deployed_app, 'hello-world.txt')
        self.assertTrue(os.path.exists(deployed_file))
