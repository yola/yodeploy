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
                                 self.root)
        config = smush_config(sources)
        write_config(config, self.root)

        super(ConfiguratedApp, self).prepare()
