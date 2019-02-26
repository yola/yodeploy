import os

from yodeploy.test_integration.helpers import rm, tests_dir
from yodeploy.test_integration.helpers import build_sample, deploy_sample
from yodeploy.test_integration.testcase import DeployTestCase


class TestNginxAppDeployment(DeployTestCase):
    def setUp(self):
        build_sample('configs')
        build_sample('nginx-app')
        deploy_sample('nginx-app')

    def tearDown(self):
        rm(os.path.join(
            tests_dir, 'filesys/etc/nginx/sites-enabled/nginx-app'))

    def test_places_server_block(self):
        self.assertDeployed('etc/nginx/sites-enabled/nginx-app')
