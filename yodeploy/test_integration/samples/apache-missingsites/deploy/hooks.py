import os
from unittest.mock import Mock

import sys

from os.path import join

from yodeploy.hooks.apache import ApacheMultiSiteApp
from yodeploy.test_integration.helpers import tests_dir

# cleans up test output, this hook is supposed to fail
sys.stderr = open(os.devnull, 'w')


class Hooks(ApacheMultiSiteApp):

    # these overrides are only needed for testsing
    apache = Mock()

    vhost_path = join(tests_dir, 'filesys', 'etc', 'apache2', 'sites-enabled')
    includes_path = join(tests_dir, 'filesys', 'etc', 'apache2', 'yola.d')

hooks = Hooks
