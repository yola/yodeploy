import getpass
import os

from mock import Mock

from yodeploy.hooks.uwsgi import UwsgiHostedApp
from yodeploy.test_integration.helpers import tests_dir


class Hooks(UwsgiHostedApp):
    # these overrides are only needed for testing
    logs_path = os.path.join(tests_dir, 'filesys/var/log/uwsgi')
    config_path = os.path.join(tests_dir, 'filesys/etc/uwsgi')
    user = getpass.getuser()
    group = None

    _reload_uwsgi = Mock()


hooks = Hooks
