import unittest

from yodeploy.hooks.apache import ApacheHostedApp, ApacheMultiSiteApp
from yodeploy.hooks.configurator import ConfiguratedApp
from yodeploy.hooks.templating import TemplatedApp


class TestApacheHostedApp(unittest.TestCase):

    def test_is_configurated(self):
        self.assertTrue(issubclass(ApacheHostedApp, ConfiguratedApp))

    def test_is_templated(self):
        self.assertTrue(issubclass(ApacheHostedApp, TemplatedApp))


class TestApacheMultiSiteApp(unittest.TestCase):

    def test_is_an_apache_hosted_app(self):
        self.assertTrue(issubclass(ApacheMultiSiteApp, ApacheHostedApp))
