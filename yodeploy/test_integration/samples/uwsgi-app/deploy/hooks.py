import getpass
import os

from mock import Mock

from yodeploy.hooks.uwsgi import UwsgiHostedApp
from yodeploy.test_integration.helpers import tests_dir


class HooksWithTestSetup(UwsgiHostedApp):
    logs_path = os.path.join(tests_dir, 'filesys/var/log/uwsgi')
    config_path = os.path.join(tests_dir, 'filesys/etc/uwsgi')
    user = getpass.getuser()
    group = None
    reload_uwsgi = Mock()


hooks = HooksWithTestSetup
