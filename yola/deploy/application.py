import logging
import os
import shutil
import subprocess

import yola.deploy.config
import yola.deploy.ipc_logging
import yola.deploy.virtualenv
from yola.deploy.util import LockFile, LockedException, extract_tar


log = logging.getLogger(__name__)


class Application(object):
    '''A deployable application.

    The deploy can be driven piece by piece, or by the deploy() function which
    will do it all in the right order.
    '''

    def __init__(self, app, target, repository, settings_file):
        self.app = app
        self.target = target
        self.repository = repository
        self.settings_fn = settings_file
        self.settings = yola.deploy.config.load_settings(settings_file)
        self.appdir = os.path.join(self.settings.paths.root, app)
        self._lock = LockFile(os.path.join(self.appdir, 'deploy.lock'))

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
        try:
            self._lock.acquire()
        except LockedException:
            raise Exception("Application locked by another deploy")

    def unlock(self):
        self._lock.release()

    def deploy_ve(self, version):
        '''Unpack a virtualenv for the deploy hooks, and return its location
        on the FS
        '''
        deploy_req_fn = os.path.join(self.appdir, 'versions', version,
                                     'deploy', 'requirements.txt')
        ve_hash = yola.deploy.virtualenv.sha224sum(deploy_req_fn)
        ve_hash = yola.deploy.virtualenv.ve_version(ve_hash)
        ve_dir = os.path.join(self.settings.paths.root, 'deploy',
                              'virtualenvs', ve_hash)
        if os.path.exists(ve_dir):
            return ve_dir
        ve_working = os.path.join(self.settings.paths.root, 'deploy',
                                  'virtualenvs', 'unpack')
        ve_unpack_root = os.path.join(ve_working, 'virtualenv')
        tarball = os.path.join(ve_working, 'virtualenv.tar.gz')
        log.debug('Deploying hook virtualenv %s', ve_hash)
        if not os.path.exists(ve_working):
            os.makedirs(ve_working)
        yola.deploy.virtualenv.download_ve(self.repository, 'deploy', ve_hash,
                                           self.target, tarball)
        extract_tar(tarball, ve_unpack_root)
        if os.path.exists(ve_dir):
            shutil.rmtree(ve_dir)
        os.rename(ve_unpack_root, ve_dir)
        return ve_dir

    def hook(self, hook, version):
        '''Run hook in the apps hooks'''
        fn = os.path.join(self.appdir, 'versions', version,
                          'deploy', 'hooks.py')
        if not os.path.isfile(fn):
            return
        ve = self.deploy_ve(version)
        # .__main__ is needed for silly Python 2.6
        # See http://bugs.python.org/issue2751
        tlss = yola.deploy.ipc_logging.ThreadedLogStreamServer()
        cmd = [os.path.join(ve, 'bin', 'python'),
               '-m', 'yola.deploy.__main__',
               '--config', self.settings_fn,
               '--app', self.app,
               '--hook', hook,
               '--log-fd', str(tlss.remote_socket.fileno()),
        ]
        if self.target:
            cmd += ['--target', self.target]
        cmd += [self.appdir, version]
        try:
            subprocess.check_call(cmd, env={
                    'PATH': os.environ['PATH'],
            })
        except subprocess.CalledProcessError:
            log.error("Hook '%s' failed %s/%s", hook, self.app, version)
            raise Exception("Hook failed")
        finally:
            tlss.shutdown()

    def deploy(self, version):
        if version is None:
            version = self.repository.latest_version(self.app, self.target)
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
            log.warn('%s/%s is the currently live version'
                     % (self.app, version))
            return
        unpack_dir = os.path.join(self.appdir, 'versions', 'unpack')
        if not os.path.isdir(unpack_dir):
            os.makedirs(unpack_dir)
        tarball = os.path.join(unpack_dir, '%s.tar.gz' % self.app)
        with self.repository.get(self.app, version, self.target) as f1:
            with open(tarball, 'w') as f2:
                shutil.copyfileobj(f1, f2)
        extract_tar(tarball, os.path.join(unpack_dir, version))
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
        self.hook('prepare', version)

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
        self.hook('deployed', version)
