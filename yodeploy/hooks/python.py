import logging
import os

from yodeploy import virtualenv
from yodeploy.hooks.base import DeployHook
from yodeploy.util import extract_tar

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
        metadata = self.repository.get_metadata(
            self.app, self.version, self.target
        )
        compat = int(metadata.get('deploy_compat', 5))
        python_version = virtualenv.get_python_version(
            compat=compat, is_deploy=False
        )
        ve_id = virtualenv.get_id(self.deploy_path('requirements.txt'),
                                  python_version,
                                  self.settings.artifacts.platform)
        ve_working = os.path.join(self.root, 'virtualenvs', 'unpack')
        ve_dir = os.path.join(self.root, 'virtualenvs', ve_id)
        tarball = os.path.join(ve_working, 'virtualenv.tar.gz')
        ve_unpack_root = os.path.join(ve_working, 'virtualenv')

        if not os.path.exists(ve_dir):
            log.debug('Deploying virtualenv %s', ve_id)

            if not os.path.exists(ve_working):
                os.makedirs(ve_working)
            virtualenv.download_ve(
                self.repository, self.app, ve_id, self.target, dest=tarball)
            extract_tar(tarball, ve_unpack_root)
            os.rename(ve_unpack_root, ve_dir)

        ve_symlink = self.deploy_path('virtualenv')
        if not os.path.exists(ve_symlink):
            os.symlink(os.path.join('..', '..', 'virtualenvs', ve_id),
                       ve_symlink)
