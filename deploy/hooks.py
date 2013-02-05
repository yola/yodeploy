import os

from yola.deploy.hooks.python import PythonApp


class Hooks(PythonApp):
    def prepare(self):
        super(Hooks, self).prepare()

        # Install our scripts into /usr/local/bin
        for fn in os.listdir(self.deploy_path('yola', 'deploy', 'cmds')):
            if fn.startswith('_') or fn.endswith('.pyc'):
                continue
            name = fn.rsplit('.', 1)[0]
            wrapper_name = os.path.join('/usr/local/bin', name)
            ve = self.deploy_path('virtualenv', 'bin', 'python')
            script = self.deploy_path('yola', 'deploy', 'cmds', fn)
            with open(wrapper_name, 'w') as f:
                f.write('#!/bin/sh\nexec %s %s "$@"\n' % (ve, script))
            os.chmod(wrapper_name, 0755)


hooks = Hooks
