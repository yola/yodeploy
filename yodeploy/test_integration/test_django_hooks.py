from yodeploy.test_integration.helpers import build_sample, deploy_sample

from yodeploy.test_integration.test_apache_hooks import ApacheTestCase
from yodeploy.test_integration.testcase import DeployTestCase


class TestDjangoAppDeployment(DeployTestCase):
    def setUp(self):
        build_sample('configs')
        build_sample('django-app')
        deploy_sample('django-app')

    def test_prepares_logfiles(self):
        self.assertDeployed('deployed/django-app/logs/app.log')
        self.assertDeployed('deployed/django-app/logs/app-celery.log')


class TestApacheHostedDjangoAppDeployment(ApacheTestCase):
    def setUp(self):
        self.clear_confs()
        build_sample('configs')
        build_sample('apache-hosted-django-app')
        deploy_sample('apache-hosted-django-app')

    def test_places_a_wsgi_handler(self):
        self.assertDeployed(
            'deployed/apache-hosted-django-app/live/'
            'apache-hosted-django-app.wsgi'
        )


class TestDjangoMultisiteDeployment(ApacheTestCase):
    def setUp(self):
        self.clear_confs()
        build_sample('configs')
        build_sample('apache-hosted-django-multisite')
        deploy_sample('apache-hosted-django-multisite')

    def test_places_a_wsgi_handler(self):
        self.assertDeployed(
            'deployed/apache-hosted-django-multisite/'
            'live/apache-hosted-django-multisite.wsgi'
        )

    def test_places_vhosts(self):
        self.assertDeployed('etc/apache2/sites-enabled/django-siteone.conf')
        self.assertDeployed('etc/apache2/sites-enabled/django-sitetwo.conf')
