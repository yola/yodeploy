import logging
import tarfile
import os

from yola.configurator.base import read_config, write_config
from yola.configurator.smush import config_sources, smush_config

from .base import DeployHook

log = logging.getLogger(__name__)


class ConfiguratedApp(DeployHook):
    def __init__(self, *args, **kwargs):
        super(ConfiguratedApp, self).__init__(*args, **kwargs)
        self.config = None

    def prepare(self):
        super(ConfiguratedApp, self).prepare()
        self.configurator_prepare()

    def deployed(self):
        super(ConfiguratedApp, self).deployed()
        self.configurator_deployed()

    def configurator_prepare(self):
        log.debug('Running ConfiguratedApp prepare hook')
        self.write_config()
        self.config = self.read_config()

    def configurator_deployed(self):
        self.config = self.read_config()

    def write_config(self):
        artifacts = self.artifacts_factory('configs.tar.gz', app='configs')
        artifacts.update_versions()
        if not artifacts.versions.latest:
            raise Exception("No configs in artifacts repository")
        app_dir = os.path.join(self.root, 'versions', self.version)
        app_conf_dir = os.path.join(app_dir, 'deploy', 'configuration')
        conf_root = os.path.join(self.settings.paths.root, 'configs')
        conf_tarball = os.path.join(conf_root, 'configs.tar.gz')
        conf_local = os.path.join(conf_root, 'local')
        # The tarball should contain a single directory called 'configs'
        configs = os.path.join(conf_root, 'configs')

        if not os.path.exists(conf_root):
            os.mkdir(conf_root)
        if not os.path.exists(conf_local):
            os.mkdir(conf_local)

        artifacts.download(conf_tarball)
        tar = tarfile.open(conf_tarball, 'r')
        try:
            tar.extractall(path=conf_root)
        finally:
            tar.close()

        sources = config_sources(self.app, self.settings.environment,
                                 self.settings.cluster,
                                 [conf_local, configs],
                                 app_conf_dir)
        config = smush_config(sources)
        write_config(config, app_dir)

    def read_config(self):
        app_dir = os.path.join(self.root, 'versions', self.version)
        return read_config(app_dir)
