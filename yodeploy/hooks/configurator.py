import json
import logging
import os
import shutil

from yoconfigurator.base import read_config, write_config
from yoconfigurator.dicts import DotDict
from yoconfigurator.filter import filter_config
from yoconfigurator.smush import config_sources, smush_config

from yodeploy.hooks.templating import TemplatedApp
from yodeploy.locking import SpinLockFile
from yodeploy.util import extract_tar

log = logging.getLogger(__name__)


class ConfiguratedApp(TemplatedApp):

    public_config_path = None

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
        self.pub_config = self.read_pub_config()
        self.inject_public_config()

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

            public_filter_pn = os.path.join(app_conf_dir, 'public-data.py')
            public_config = filter_config(config, public_filter_pn)

        write_config(config, self.deploy_dir)
        if public_config:
            write_config(
                public_config, self.deploy_dir, 'configuration_public.json')

    def read_config(self):
        return read_config(self.deploy_dir)

    def read_pub_config(self):
        path = os.path.join(self.deploy_dir, 'configuration_public.json')
        if not os.path.isfile(path):
            return DotDict()
        with open(path, 'r') as f:
            return DotDict(json.load(f))

    def inject_public_config(self):
        """Replace the config token with serialized public config."""
        if not self.public_config_path:
            return
        path = self.deploy_path(self.public_config_path)
        pub_conf_json = json.dumps(self.pub_config)
        with open(path, 'r') as f:
            content = f.read()
        content = content.replace('<%= config %>', pub_conf_json)
        with open(path, 'w') as f:
            f.write(content)
