import os

from yodeploy.test_integration.helpers import (
    build_sample, deploy_sample, rmdir)
from yodeploy.test_integration.testcase import DeployTestCase


class ApacheTestCase(DeployTestCase):
    def clear_confs(self):
        apache = os.path.join(
            os.path.dirname(__file__), 'filesys', 'etc', 'apache2')
        for file in os.listdir(os.path.join(apache, 'sites-enabled')):
            if not file.startswith('.'):
                os.unlink(os.path.join(apache, 'sites-enabled', file))
        for d in os.listdir(os.path.join(apache, 'yola.d')):
            if not d.startswith('.'):
                rmdir(os.path.join(apache, 'yola.d', d))


class TestApacheHostedAppDeployment(ApacheTestCase):

    def setUp(self):
        self.clear_confs()
        build_sample('configs')
        build_sample('apache-app')
        build_sample('apache-missingconfs')
        deploy_sample('apache-app')

    def test_places_a_vhost(self):
        self.assertDeployed('etc/apache2/sites-enabled/apache-app.conf')

    def test_places_includes(self):
        self.assertDeployed('etc/apache2/yola.d/apache-app/redirects')
        self.assertDeployed('etc/apache2/yola.d/apache-app/headers')

    def test_blows_up_if_missing_vhost_template(self):
        with self.assertRaises(Exception):
            deploy_sample('apache-missingconfs')


class TestApacheMultiSiteAppDeployment(ApacheTestCase):

    def setUp(self):
        self.clear_confs()
        build_sample('configs')
        build_sample('apache-missingsites')
        build_sample('apache-whitelabel')
        deploy_sample('apache-whitelabel')

    def test_places_all_vhosts(self):
        self.assertDeployed('etc/apache2/sites-enabled/appname-wl')
        self.assertDeployed('etc/apache2/sites-enabled/appname')

    def test_blows_up_if_missing_vhosts(self):
        with self.assertRaises(Exception):
            deploy_sample('apache-missingsites')
