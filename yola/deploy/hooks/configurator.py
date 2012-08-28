import logging
import os
import shutil

from yola.configurator.base import read_config, write_config
from yola.configurator.smush import config_sources, smush_config

from ..util import extract_tar
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
        app_conf_dir = self.deploy_path('deploy', 'configuration')
        conf_root = os.path.join(self.settings.paths.root, 'configs')
        conf_tarball = os.path.join(conf_root, 'configs.tar.gz')
        # TODO: Get this from settings
        conf_local = '/etc/yola/deployconfigs/chef/'
        # The tarball should contain a single directory called 'configs'
        configs = os.path.join(conf_root, 'configs')

        if not os.path.exists(conf_root):
            os.mkdir(conf_root)
        if not os.path.exists(conf_local):
            os.makedirs(conf_local)
        if os.path.exists(configs):
            shutil.rmtree(configs)

        artifacts.download(conf_tarball)
        extract_tar(conf_tarball, configs)
        os.unlink(conf_tarball)

        sources = config_sources(self.app, self.settings.environment,
                                 self.settings.cluster,
                                 [conf_local, configs],
                                 app_conf_dir)
        config = smush_config(sources)
        write_config(config, self.deploy_dir)

    def read_config(self):
        return read_config(self.deploy_dir)
