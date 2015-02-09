from yodeploy.test_integration.helpers import build_sample, deploy_sample

from yodeploy.test_integration.test_apache_hooks import ApacheTestCase


class TestDjangoAppDeployment(ApacheTestCase):

    def setUp(self):
        self.clear_confs()
        build_sample('configs')
        build_sample('django-app')
        deploy_sample('django-app')

    def test_places_a_wsgi_handler(self):
        self.assertDeployed('deployed/django-app/live/django-app.wsgi')


class TestDjangoMultisiteDeployment(ApacheTestCase):

    def setUp(self):
        self.clear_confs()
        build_sample('configs')
        build_sample('django-multisite')
        deploy_sample('django-multisite')

    def test_places_a_wsgi_handler(self):
        self.assertDeployed(
            'deployed/django-multisite/live/django-multisite.wsgi')

    def test_places_vhosts(self):
        self.assertDeployed('etc/apache2/sites-enabled/django-siteone.conf')
        self.assertDeployed('etc/apache2/sites-enabled/django-sitetwo.conf')
