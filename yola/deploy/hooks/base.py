import os


class DeployHook(object):
    def __init__(self, app, target, root, version, settings,
                 artifacts_factory):
        self.app = app
        self.target = target
        # The root of this application's area:
        self.root = root
        # The version being deployed:
        self.version = version
        # deploy_settings
        self.settings = settings
        self.artifacts_factory = artifacts_factory

    def prepare(self):
        '''Hook called after unpacking, before swinging the symlink'''
        pass

    def deployed(self):
        '''Hook called after swinging the symlink'''
        pass

    @property
    def deploy_dir(self):
        '''The directory we are deploying into'''
        return os.path.join(self.root, 'versions', self.version)

    def deploy_path(self, *args):
        '''Convenince function combinig deploy_dir and os.path.join'''
        return os.path.join(self.deploy_dir, *args)
