import os

from yodeploy.hooks.configurator import ConfiguratedApp
from yodeploy.hooks.daemon import DaemonApp
from yodeploy.hooks.python import PythonApp


class Hooks(ConfiguratedApp, PythonApp, DaemonApp):
    def prepare(self):
        super(Hooks, self).prepare()

        # Install our scripts into /usr/local/bin
        for fn in os.listdir(self.deploy_path('yodeploy', 'cmds')):
            if fn.startswith('_') or not fn.endswith('.py'):
                continue
            name = fn.rsplit('.', 1)[0].replace('_', '-')
            wrapper_name = os.path.join('/usr/local/bin', name)
            ve = self.deploy_path('virtualenv', 'bin', 'python')
            script = self.deploy_path('yodeploy', 'cmds', fn)
            if os.path.exists(wrapper_name):
                # Remove existing symlinks
                os.unlink(wrapper_name)
            with open(wrapper_name, 'w') as f:
                f.write('#!/bin/sh\nexec %s %s "$@"\n' % (ve, script))
            os.chmod(wrapper_name, 0o755)

        logdir = '/var/log/deploy'
        if not os.path.exists(logdir):
            os.mkdir(logdir)


hooks = Hooks
