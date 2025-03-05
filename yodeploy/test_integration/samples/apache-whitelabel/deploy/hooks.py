from unittest.mock import Mock

from os.path import join

from yodeploy.hooks.apache import ApacheMultiSiteApp
from yodeploy.test_integration.helpers import tests_dir


class Hooks(ApacheMultiSiteApp):

    # these overrides are only needed for testsing
    apache = Mock()

    vhost_path = join(tests_dir, 'filesys', 'etc', 'apache2', 'sites-enabled')
    includes_path = join(tests_dir, 'filesys', 'etc', 'apache2', 'yola.d')

hooks = Hooks
