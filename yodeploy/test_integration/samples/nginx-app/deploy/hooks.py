import getpass

import mock

from os.path import join

from yodeploy.hooks.nginx import NginxHostedApp
from yodeploy.test_integration.helpers import tests_dir


class Hooks(NginxHostedApp):
    # these overrides are only needed for testing
    nginx = mock.Mock()
    logs_path = join(tests_dir, 'filesys/var/log/nginx')
    server_blocks_path = join(tests_dir, 'filesys/etc/nginx/sites-enabled')
    user = getpass.getuser()
    group = None


hooks = Hooks
