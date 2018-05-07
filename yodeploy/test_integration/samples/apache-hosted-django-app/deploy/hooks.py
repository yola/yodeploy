import getpass
import os

import mock

from yodeploy.hooks.django import ApacheHostedDjangoApp
from yodeploy.test_integration.helpers import tests_dir


class Hooks(ApacheHostedDjangoApp):
    # these overrides are only needed for testing
    apache = mock.Mock()
    vhost_path = os.path.join(
        tests_dir, 'filesys', 'etc', 'apache2', 'sites-enabled'
    )
    includes_path = os.path.join(
        tests_dir, 'filesys', 'etc', 'apache2', 'yola.d'
    )
    log_user = getpass.getuser()
    log_group = None


hooks = Hooks
