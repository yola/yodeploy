import logging
import os
import subprocess
import sys

from yodeploy.hooks.configurator import ConfiguratedApp
from yodeploy.util import touch

log = logging.getLogger(__name__)


class NginxHostedApp(ConfiguratedApp):
    logs_path = '/var/log/nginx/'
    server_blocks_path = '/etc/nginx/sites-enabled'
    user = 'www-data'
    group = 'adm'

    def deployed(self):
        super(NginxHostedApp, self).deployed()
        self.nginx_hosted_deployed()

    def prepare(self):
        super(NginxHostedApp, self).prepare()
        self.nginx_hosted_prepare()

    def nginx_hosted_prepare(self):
        log.debug('Running NginxHostedApp prepare hook.')
        access_log_path = os.path.join(
            self.logs_path, '{}-access.log'.format(self.app)
        )
        error_log_path = os.path.join(
            self.logs_path, '{}-error.log'.format(self.app)
        )
        touch(access_log_path, self.user, self.group, 0o640)
        touch(error_log_path, self.user, self.group, 0o640)
        self.template(
            'nginx/server_block.conf.template',
            os.path.join(self.server_blocks_path, self.app)
        )

    def nginx_hosted_deployed(self):
        log.debug('Running NginxHostedApp deployed hook.')
        self.reload_nginx()

    def reload_nginx(self):
        try:
            subprocess.check_call(('service', 'nginx', 'reload'))
        except subprocess.CalledProcessError:
            log.exception('Unable to reload nginx.')
            sys.exit(1)
