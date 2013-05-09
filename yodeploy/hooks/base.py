import os


class DeployHook(object):
    def __init__(self, app, target, root, version, settings,
                 repository):
        self.app = app
        self.target = target
        # The root of this application's area:
        self.root = root
        # The version being deployed:
        self.version = version
        # deploy_settings
        self.settings = settings
        self.repository = repository

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
        '''Convenience function combining deploy_dir and os.path.join'''
        return os.path.join(self.deploy_dir, *args)
