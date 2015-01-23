import mock

from os.path import join

from yodeploy.hooks.apache import ApacheHostedApp
from yodeploy.tests.samples.helpers import tests_dir


class Hooks(ApacheHostedApp):

    # these overrides are only needed for testsing
    apache = mock.Mock()
    vhost_path = join(tests_dir, 'filesys', 'etc', 'apache2', 'sites-enabled')
    includes_path = join(tests_dir, 'filesys', 'etc', 'apache2', 'yola.d')

hooks = Hooks
