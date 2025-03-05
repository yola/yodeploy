import getpass
import os

from unittest.mock import Mock

from yodeploy.hooks.nginx import NginxHostedApp
from yodeploy.test_integration.helpers import tests_dir


class HooksWithTestSetup(NginxHostedApp):
    logs_path = os.path.join(tests_dir, 'filesys/var/log/nginx')
    server_blocks_path = os.path.join(
        tests_dir, 'filesys/etc/nginx/sites-enabled'
    )
    user = getpass.getuser()
    group = None
    _reload_nginx = Mock()


hooks = HooksWithTestSetup
