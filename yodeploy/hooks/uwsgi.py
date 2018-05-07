import logging
import os
import subprocess
import sys

from yodeploy.hooks.configurator import ConfiguratedApp
from yodeploy.util import touch

log = logging.getLogger(__name__)


class UwsgiHostedApp(ConfiguratedApp):
    config_path = '/etc/uwsgi/'
    logs_path = '/var/log/uwsgi/'
    user = 'www-data'
    group = 'adm'

    def deployed(self):
        super(UwsgiHostedApp, self).deployed()
        self.uwsgi_hosted_deployed()

    def prepare(self):
        super(UwsgiHostedApp, self).prepare()
        self.uwsgi_hosted_prepare()

    def uwsgi_hosted_prepare(self):
        log.debug('Running UwsgiHostedApp prepare hook.')
        log_path = os.path.join(
            self.logs_path, '{}.log'.format(self.app)
        )
        touch(log_path, self.user, self.group, 0o640)

        self.template(
            'uwsgi/config.ini.template',
            os.path.join(self.config_path, '{}.ini'.format(self.app)),
        )

    def uwsgi_hosted_deployed(self):
        log.debug('Running UwsgiHostedApp deployed hook.')
        self.reload_uwsgi()

    def reload_uwsgi(self):
        try:
            subprocess.check_call(('service', 'uwsgi', 'reload'))
        except subprocess.CalledProcessError:
            log.exception('Unable to reload uwsgi.')
            sys.exit(1)
