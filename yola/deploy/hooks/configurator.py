import logging
import tarfile
import os
from yola.configurator.smush import config_sources, smush_config, write_config

from .base import DeployHook

log = logging.getLogger(__name__)


class ConfiguratedApp(DeployHook):
    def prepare(self):
        artifacts = self.artifacts_factory('configs.tar.gz', app='configs')
        artifacts.update_versions()
        if not artifacts.versions.latest:
            raise Exception("No configs in artifacts repository")
        conf_tarball = os.path.join(self.settings.paths.settings, 'configs.tar.gz')
        artifacts.download(conf_tarball)
        tar = tarfile.open(conf_tarball, 'r')
        tar.extractall(path=self.settings.paths.settings)
        tar.close()
        sources = config_sources(self.app, self.settings.environment, self.settings.cluster, [self.settings.paths.settings], self.root)
        config = smush_config(sources)
        write_config(config, self.root)
        super(ConfiguratedApp, self).prepare()
