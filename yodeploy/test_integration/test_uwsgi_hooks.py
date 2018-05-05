from os.path import join

from yodeploy.test_integration.helpers import rm, tests_dir
from yodeploy.test_integration.helpers import build_sample, deploy_sample
from yodeploy.test_integration.testcase import DeployTestCase


class TestUwsgiAppDeployment(DeployTestCase):
    def setUp(self):
        build_sample('configs')
        build_sample('uwsgi-app')
        deploy_sample('uwsgi-app')

    def tearDown(self):
        rm(join(tests_dir, 'filesys/var/log/uwsgi/usgi-app.log'))
        rm(join(tests_dir, 'filesys/etc/uwsgi/uwsgi-app.ini'))

    def test_places_config_ini(self):
        self.assertDeployed('etc/uwsgi/uwsgi-app.ini')

    def test_places_logfiles(self):
        self.assertDeployed('var/log/uwsgi/uwsgi-app.log')
