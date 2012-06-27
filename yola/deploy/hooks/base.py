class DeployHook(object):
    def __init__(self, app, env, root, version, metadata):
        self.app = app
        self.env = env
        self.root = root
        self.version = version
        self.metadata = metadata

    def prepare(self):
        '''Hook called after unpacking, before swinging the symlink'''
        pass

    def deployed(self):
        '''Hook called after swinging the symlink'''
        pass
