import logging
import os
import shutil

from .base import DeployHook
from ..util import extract_tar
from ..virtualenv import ve_version, sha224sum, download_ve

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
        ve_hash = ve_version(sha224sum(self.deploy_path('requirements.txt')))
        ve_working = os.path.join(self.root, 'virtualenvs', 'unpack')
        ve_dir = os.path.join(self.root, 'virtualenvs', ve_hash)
        tarball = os.path.join(ve_working, 'virtualenv.tar.gz')

        log.debug('Deploying virtualenv %s', ve_hash)

        if not os.path.exists(ve_working):
            os.makedirs(ve_working)
        if not download_ve(self.app, ve_hash, self.artifacts_factory,
                           tarball):
            raise Exception("Could not locate virtualenv %s" % ve_hash)
        extract_tar(tarball, ve_working)
        if os.path.exists(ve_dir):
            shutil.rmtree(ve_dir)
        os.rename(ve_working, ve_dir)
        os.symlink(os.path.join('..', '..', 'virtualenvs', ve_hash),
                   self.deploy_path('virtualenv'))
