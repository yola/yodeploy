import errno
import logging
import os
import shutil
import subprocess

import yodeploy.config
import yodeploy.ipc_logging
from yodeploy import virtualenv
from yodeploy.locking import LockFile, SpinLockFile
from yodeploy.repository import version_sort_key
from yodeploy.util import extract_tar, ignoring


log = logging.getLogger(__name__)


class Application(object):
    """A deployable application.

    The deploy can be driven piece by piece, or by the deploy() function which
    will do it all in the right order.
    """

    def __init__(self, app, settings_file):
        self.app = app
        self.settings_fn = settings_file
        self.settings = yodeploy.config.load_settings(settings_file)
        self.appdir = os.path.join(self.settings.paths.apps, app)
        if not os.path.isdir(self.appdir):
            os.makedirs(self.appdir)
        self.lock = LockFile(os.path.join(self.appdir, 'deploy.lock'))
        self.compat = self.live_compat

    @property
    def live_version(self):
        '''Currently deployed version'''
        live_link = os.path.join(self.appdir, 'live')
        if not os.path.exists(live_link):
            return None
        dest = os.readlink(live_link).split('/')
        if len(dest) == 2 and dest[0] == 'versions':
            return dest[1]

    @property
    def live_compat(self):
        """Currently deployed version's compat level"""
        compat_file = os.path.join(self.appdir, 'live', 'deploy', 'compat')
        if not os.path.exists(compat_file):
            return None
        with open(compat_file) as f:
            return int(f.read())

    @property
    def deployed_versions(self):
        version_dir = os.path.join(self.appdir, 'versions')
        return sorted((version for version in os.listdir(version_dir)
                       if version != 'unpack'),
                      key=version_sort_key)

    def deploy_ve(self, target, repository, app_version):
        """Prepare the deploy virtualenv.

        Unpack a virtualenv for the deploy hooks, and return its location on
        the FS.
        """
        deploy_req_fn = os.path.join(self.appdir, 'versions', app_version,
                                     'deploy', 'requirements.txt')
        python_version = virtualenv.get_python_version(self.compat)
        platform = self.settings.artifacts.platform
        ve_id = virtualenv.get_id(deploy_req_fn, python_version, platform)
        ves_dir = os.path.join(self.settings.paths.apps, 'deploy',
                               'virtualenvs')
        ve_dir = os.path.join(ves_dir, ve_id)
        if os.path.exists(ve_dir):
            return ve_dir
        ve_working = os.path.join(ves_dir, 'unpack')
        if not os.path.exists(ve_working):
            os.makedirs(ve_working)
        ve_unpack_root = os.path.join(ve_working, 'virtualenv')
        tarball = os.path.join(ve_working, 'virtualenv.tar.gz')
        with SpinLockFile(os.path.join(ves_dir, 'deploy.lock'), timeout=30):
            log.debug('Deploying hook virtualenv %s', ve_id)
            virtualenv.download_ve(
                repository, 'deploy', ve_id, target, tarball)
            extract_tar(tarball, ve_unpack_root)
            if os.path.exists(ve_dir):
                shutil.rmtree(ve_dir)
            os.rename(ve_unpack_root, ve_dir)
        return ve_dir

    def hook(self, hook, target, repository, version):
        '''Run hook in the apps hooks'''
        fn = os.path.join(self.appdir, 'versions', version,
                          'deploy', 'hooks.py')
        if not os.path.isfile(fn):
            return

        ve = self.deploy_ve(target, repository, version)
        tlss = yodeploy.ipc_logging.ThreadedLogStreamServer()
        cmd = [os.path.join(ve, 'bin', 'python'),
               '-m', 'yodeploy',
               '--config', self.settings_fn,
               '--app', self.app,
               '--hook', hook,
               '--log-fd', str(tlss.remote_socket.fileno()),
        ]
        if target:
            cmd += ['--target', target]
        cmd += [self.appdir, version]

        env = {
            'PATH': os.environ['PATH'],
        }

        try:
            subprocess.check_call(cmd, env=env, close_fds=False)
        except subprocess.CalledProcessError:
            log.error("Hook '%s' failed %s/%s", hook, self.app, version)
            raise Exception("Hook failed")
        finally:
            tlss.shutdown()

    def deploy(self, target, repository, version):
        if version is None:
            version = repository.latest_version(self.app, self.target)
        log.info('Deploying %s/%s', self.app, version)
        with self.lock:
            self.unpack(target, repository, version)
            self.prepare(target, repository, version)
            self.swing_symlink(version)
            self.deployed(target, repository, version)
        log.info('Deployed %s/%s', self.app, version)

    def unpack(self, target, repository, version):
        """First stage of deployment"""
        assert self.lock.held
        log.debug('Unpacking %s/%s', self.app, version)

        if self.live_version == version:
            log.warn('%s/%s is the currently live version'
                     % (self.app, version))
            return
        unpack_dir = os.path.join(self.appdir, 'versions', 'unpack')
        if not os.path.isdir(unpack_dir):
            os.makedirs(unpack_dir)
        tarball = os.path.join(unpack_dir, '%s.tar.gz' % self.app)

        with repository.get(self.app, version, target) as f1:
            self.compat = int(f1.metadata.get('deploy_compat', 1))
            if self.compat not in (4, 5):
                raise Exception('Unsupported artifact: compat level %s'
                                % self.compat)
            with open(tarball, 'wb') as f2:
                shutil.copyfileobj(f1, f2)

        extract_tar(tarball, os.path.join(unpack_dir, version))
        os.unlink(tarball)
        staging = os.path.join(self.appdir, 'versions', version)
        if os.path.isdir(staging):
            shutil.rmtree(staging)
        os.rename(os.path.join(self.appdir, 'versions', 'unpack', version),
                  staging)

    def prepare(self, target, repository, version):
        """Post-unpack, pre-swing hook"""
        assert self.lock.held
        log.debug('Preparing %s/%s', self.app, version)
        self.hook('prepare', target, repository, version)

    def swing_symlink(self, version):
        """Make version live"""
        assert self.lock.held
        log.debug('Swinging %s/%s', self.app, version)
        # rename is atomic, symlink isn't
        link = os.path.join(self.appdir, 'live')
        temp_link = os.path.join(self.appdir, 'live.new')
        if os.path.exists(temp_link):
            os.unlink(temp_link)
        os.symlink(os.path.join('versions', version), temp_link)
        os.rename(temp_link, link)

    def deployed(self, target, repository, version):
        """Post-swing hook"""
        assert self.lock.held
        log.debug('Deployed hook %s/%s', self.app, version)
        self.hook('deployed', target, repository, version)

    def gc(self, max_versions):
        """Garbage-collect artifacts.

        Remove all deployed versions except the most recent max_versions, and
        any live verisons.
        """
        with self.lock:
            old_versions = set(self.deployed_versions[:-max_versions])
            if self.live_version:
                old_versions.discard(self.live_version)

                # We bootstrap environments that have their own Jenkins, from
                # the production repository. So there is likely to be 1 (and
                # only 1) version higher than the local builds, but older.
                mtime = lambda version: os.stat(
                    os.path.join(self.appdir, 'versions', version)).st_mtime
                last_version = self.deployed_versions[-1]
                if (self.live_version != last_version and
                        mtime(self.live_version) > mtime(last_version)):
                    old_versions.add(last_version)

            for version in old_versions:
                shutil.rmtree(os.path.join(self.appdir, 'versions', version))

            used_virtualenvs = set()
            for version in self.deployed_versions:
                ve = os.path.join(self.appdir, 'versions', version,
                                  'virtualenv')
                with ignoring(errno.ENOENT):
                    used_virtualenvs.add(os.path.basename(os.readlink(ve)))

            ve_dir = os.path.join(self.appdir, 'virtualenvs')
            if os.path.isdir(ve_dir):
                for ve in os.listdir(ve_dir):
                    if ve not in used_virtualenvs:
                        shutil.rmtree(os.path.join(ve_dir, ve))
