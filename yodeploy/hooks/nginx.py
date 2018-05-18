import logging
import os
import subprocess
import sys

from yodeploy.hooks.configurator import ConfiguratedApp

log = logging.getLogger(__name__)


class NginxHostedApp(ConfiguratedApp):
    server_blocks_path = '/etc/nginx/sites-enabled'

    def deployed(self):
        super(NginxHostedApp, self).deployed()
        self.nginx_hosted_deployed()

    def prepare(self):
        super(NginxHostedApp, self).prepare()
        self.nginx_hosted_prepare()

    def nginx_hosted_prepare(self):
        log.debug('Running NginxHostedApp prepare hook.')
        self.template(
            'nginx/server-block.template',
            os.path.join(self.server_blocks_path, self.app)
        )

    def nginx_hosted_deployed(self):
        log.debug('Running NginxHostedApp deployed hook.')
        self._reload_nginx()

    def _reload_nginx(self):
        try:
            subprocess.check_call(('service', 'nginx', 'reload'))
        except subprocess.CalledProcessError:
            log.exception('Unable to reload nginx.')
            sys.exit(1)
