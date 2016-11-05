import os

from yodeploy.hooks.base import DeployHook


class Hooks(DeployHook):
    def prepare(self):
        open(os.path.join(self.root, 'prepare_hook_output'), 'w').close()

    def deployed(self):
        open(os.path.join(self.root, 'deployed_hook_output'), 'w').close()


hooks = Hooks
