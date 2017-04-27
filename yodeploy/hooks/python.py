import logging
import os

from yodeploy.hooks.base import DeployHook
from yodeploy.util import extract_tar
from yodeploy.virtualenv import ve_version, sha224sum, download_ve

log = logging.getLogger(__name__)


class PythonApp(DeployHook):
    def prepare(self):
        super(PythonApp, self).prepare()
        self.python_prepare()

    def python_prepare(self):
        log.debug('Running PythonApp prepare hook')
        requirements = self.deploy_path('requirements.txt')
        if os.path.exists(requirements):
            self.deploy_ve()

    def deploy_ve(self):
        log = logging.getLogger(__name__)
        hash_ = sha224sum(self.deploy_path('requirements.txt'))
        version = ve_version(hash_, self.settings.artifacts.platform)
        ve_working = os.path.join(self.root, 'virtualenvs', 'unpack')
        ve_dir = os.path.join(self.root, 'virtualenvs', version)
        tarball = os.path.join(ve_working, 'virtualenv.tar.gz')
        ve_unpack_root = os.path.join(ve_working, 'virtualenv')

        if not os.path.exists(ve_dir):
            log.debug('Deploying virtualenv %s', version)

            if not os.path.exists(ve_working):
                os.makedirs(ve_working)
            download_ve(self.repository, self.app, version, self.target,
                        dest=tarball)
            extract_tar(tarball, ve_unpack_root)
            os.rename(ve_unpack_root, ve_dir)

        ve_symlink = self.deploy_path('virtualenv')
        if not os.path.exists(ve_symlink):
            os.symlink(os.path.join('..', '..', 'virtualenvs', version),
                       ve_symlink)
