import getpass
from unittest.mock import Mock

from os.path import join

from yodeploy.hooks.django import ApacheHostedDjangoApp
from yodeploy.test_integration.helpers import tests_dir


class Hooks(ApacheHostedDjangoApp):

    # these overrides are only needed for testsing
    apache = Mock()

    vhost_path = join(tests_dir, 'filesys', 'etc', 'apache2', 'sites-enabled')
    includes_path = join(tests_dir, 'filesys', 'etc', 'apache2', 'yola.d')
    log_user = getpass.getuser()
    log_group = None

hooks = Hooks
