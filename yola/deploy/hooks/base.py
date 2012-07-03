class DeployHook(object):
    def __init__(self, app, target, root, version, settings,
                 artifacts_factory):
        self.app = app
        self.target = target
        self.root = root
        self.version = version
        self.settings = settings
        self.artifacts_factory = artifacts_factory

    def prepare(self):
        '''Hook called after unpacking, before swinging the symlink'''
        pass

    def deployed(self):
        '''Hook called after swinging the symlink'''
        pass
