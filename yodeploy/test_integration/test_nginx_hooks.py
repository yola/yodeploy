from os.path import join

from yodeploy.test_integration.helpers import rm, tests_dir
from yodeploy.test_integration.helpers import build_sample, deploy_sample
from yodeploy.test_integration.testcase import DeployTestCase


class TestNginxAppDeployment(DeployTestCase):
    def setUp(self):
        build_sample('configs')
        build_sample('nginx-app')
        deploy_sample('nginx-app')

    def tearDown(self):
        rm(join(tests_dir, 'filesys/var/log/nginx/nginx-app-access.log'))
        rm(join(tests_dir, 'filesys/var/log/nginx/nginx-app-error.log'))
        rm(join(tests_dir, 'filesys/etc/nginx/sites-enabled/nginx-app'))

    def test_places_server_block(self):
        self.assertDeployed('etc/nginx/sites-enabled/nginx-app')

    def test_places_logfiles(self):
        self.assertDeployed('var/log/nginx/nginx-app-access.log')
        self.assertDeployed('var/log/nginx/nginx-app-error.log')
