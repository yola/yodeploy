import fcntl
import imp
import logging
import os
import shutil
import tarfile


log = logging.getLogger(__name__)


class Application(object):
    'A deployable application'

    def __init__(self, app, environment, artifacts_factory, deploy_root,
                 artifacts=None):
        self.app = app
        self.environment = environment
        self.artifacts_factory = artifacts_factory
        if artifacts is None:
            artifacts = artifacts_factory()
        self.artifacts = artifacts
        self.appdir = os.path.join(deploy_root, app)
        self._lock = None

    @property
    def live_version(self):
        '''Currently deployed version'''
        live_link = os.path.join(self.appdir, 'live')
        if not os.path.exists(live_link):
            return None
        dest = os.readlink(live_link).split('/')
        if len(dest) == 2 and dest[0] == 'versions':
            return dest[1]

    def lock(self):
        '''Take a lock on the application'''
        if not os.path.isdir(self.appdir):
            os.makedirs(self.appdir)
        self._lock = os.open(os.path.join(self.appdir, 'deploy.lock'),
                             os.O_CREAT | os.O_WRONLY, 0600)
        try:
            fcntl.lockf(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise Exception("Application locked by another deploy")

    def unlock(self):
        fcntl.lockf(self._lock, fcntl.LOCK_UN)
        os.unlink(os.path.join(self.appdir, 'deploy.lock'))
        os.close(self._lock)
        self._lock = None

    def _extract(self, tarball, root):
        '''Extract a tarball into its parent directory, rename the extracted
        root directory to root.
        '''
        workdir = os.path.dirname(tarball)
        tar = tarfile.open(tarball, 'r')
        roots = set(name.split('/', 1)[0] for name in tar.getnames())
        if len(roots) > 1:
            raise Exception("Tarball has more than one top-level directory")
        tar.extractall(path=workdir)
        tar.close()

        extracted_root = os.path.join(workdir, list(roots)[0])
        root = os.path.join(workdir, root)
        if os.path.isdir(root):
            shutil.rmtree(root)
        os.rename(extracted_root, root)

    def _hook(self, hook, version):
        '''Run hook in the apps hooks'''
        fake_mod = '_deploy_hooks'
        fn = os.path.join(self.appdir, 'versions', version,
                          'deploy', 'hooks.py')
        if os.path.isfile(fn):
            description = ('.py', 'r', imp.PY_SOURCE)
            with open(fn) as f:
                m = imp.load_module(fake_mod, f, fn, description)
            hooks = getattr(m, 'hooks')(
                    self.app, self.environment, self.appdir, version,
                    self.artifacts_factory)
            getattr(hooks, hook)()

    def deploy(self, version):
        log.info('Deploying %s/%s', self.app, version)
        self.lock()
        self.unpack(version)
        self.prepare(version)
        self.swing_symlink(version)
        self.deployed(version)
        self.unlock()
        log.info('Deployed %s/%s', self.app, version)

    def unpack(self, version):
        '''First stage of deployment'''
        assert self._lock is not None
        log.debug('Unpacking %s/%s', self.app, version)

        if self.live_version == version:
            # TODO: Handle this, it's useful for testing
            raise Exception('%s/%s is the currently live version'
                            % (self.app, version))
        unpack_dir = os.path.join(self.appdir, 'versions', 'unpack')
        if not os.path.isdir(unpack_dir):
            os.makedirs(unpack_dir)
        tarball = os.path.join(unpack_dir, self.artifacts.filename)
        # TODO: Migrate to git hashes everywhere
        self.artifacts.download(target=tarball, version=version)
        self._extract(tarball, version)
        os.unlink(tarball)
        staging = os.path.join(self.appdir, 'versions', version)
        if os.path.isdir(staging):
            shutil.rmtree(staging)
        os.rename(os.path.join(self.appdir, 'versions', 'unpack', version),
                  staging)

    def prepare(self, version):
        '''Post-unpack, pre-swing hook'''
        assert self._lock is not None
        log.debug('Preparing %s/%s', self.app, version)
        self._hook('prepare', version)

    def swing_symlink(self, version):
        '''Make version live'''
        assert self._lock is not None
        log.debug('Swinging %s/%s', self.app, version)
        # rename is atomic, symlink isn't
        link = os.path.join(self.appdir, 'live')
        temp_link = os.path.join(self.appdir, 'live.new')
        if os.path.exists(temp_link):
            os.unlink(temp_link)
        os.symlink(os.path.join('versions', version), temp_link)
        os.rename(temp_link, link)

    def deployed(self, version):
        '''Post-swing hook'''
        assert self._lock is not None
        log.debug('Deployed hook %s/%s', self.app, version)
        self._hook('deployed', version)
