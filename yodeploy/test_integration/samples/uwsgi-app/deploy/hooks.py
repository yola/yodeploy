import getpass

import mock

from os.path import join

from yodeploy.hooks.uwsgi import UwsgiHostedApp
from yodeploy.test_integration.helpers import tests_dir


class Hooks(UwsgiHostedApp):
    # these overrides are only needed for testing
    uwsgi = mock.Mock()
    logs_path = join(tests_dir, 'filesys/var/log/uwsgi')
    config_path = join(tests_dir, 'filesys/etc/uwsgi')
    user = getpass.getuser()
    group = None

hooks = Hooks
