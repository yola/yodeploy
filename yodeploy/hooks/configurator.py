import logging
import os
import shutil

from yoconfigurator.base import read_config, write_config
from yoconfigurator.smush import config_sources, smush_config

from ..locking import SpinLockFile
from ..util import extract_tar
from .base import DeployHook

log = logging.getLogger(__name__)


class ConfiguratedApp(DeployHook):
    def __init__(self, *args, **kwargs):
        super(ConfiguratedApp, self).__init__(*args, **kwargs)
        self.config = None

    def prepare(self):
        self.configurator_prepare()
        super(ConfiguratedApp, self).prepare()

    def deployed(self):
        self.configurator_deployed()
        super(ConfiguratedApp, self).deployed()

    def configurator_prepare(self):
        log.debug('Running ConfiguratedApp prepare hook')
        self.write_config()
        self.config = self.read_config()

    def configurator_deployed(self):
        self.config = self.read_config()

    def write_config(self):
        conf_root = os.path.join(self.settings.paths.apps, 'configs')
        if not os.path.exists(conf_root):
            os.mkdir(conf_root)
        conf_tarball = os.path.join(conf_root, 'configs.tar.gz')
        with SpinLockFile(os.path.join(conf_root, 'deploy.lock'), timeout=30):
            try:
                with self.repository.get('configs', target='master') as f1:
                    with open(conf_tarball, 'w') as f2:
                        shutil.copyfileobj(f1, f2)
            except KeyError:
                raise Exception("No configs in artifacts repository")

            configs = os.path.join(conf_root, 'configs')
            if os.path.exists(configs):
                shutil.rmtree(configs)

            extract_tar(conf_tarball, configs)
            os.unlink(conf_tarball)

            configs_dirs = [configs] + self.settings.deployconfigs.overrides
            app_conf_dir = self.deploy_path('deploy', 'configuration')
            sources = config_sources(self.app,
                                     self.settings.artifacts.environment,
                                     self.settings.artifacts.cluster,
                                     configs_dirs, app_conf_dir)
            config = smush_config(
                sources, initial={'yoconfigurator': {'app': self.app}})
        write_config(config, self.deploy_dir)

    def read_config(self):
        return read_config(self.deploy_dir)
