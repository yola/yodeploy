import getpass
import os

from mock import Mock

from yodeploy.hooks.nginx import NginxHostedApp
from yodeploy.test_integration.helpers import tests_dir


class Hooks(NginxHostedApp):
    # these overrides are only needed for testing
    logs_path = os.path.join(tests_dir, 'filesys/var/log/nginx')
    server_blocks_path = os.path.join(
        tests_dir, 'filesys/etc/nginx/sites-enabled'
    )
    user = getpass.getuser()
    group = None

    _reload_nginx = Mock()


hooks = Hooks
