import errno
import logging
import os

from yodeploy.hooks.apache import ApacheHostedApp, ApacheMultiSiteApp
from yodeploy.hooks.configurator import ConfiguratedApp
from yodeploy.util import chown_r, ignoring, touch


log = logging.getLogger(__name__)


class DockerDjangoApp(ConfiguratedApp):
    has_static = False
    log_user = 'www-data'
    log_group = 'adm'

    def prepare(self):
        super(DockerDjangoApp, self).prepare()
        self.docker_django_prepare()

    def deployed(self):
        self.docker_django_deployed()
        super(DockerDjangoApp, self).deployed()

    def prepare_logfiles(self):
        path = self.config.get(self.app, {}).get('path', {})
        logs = [path.get('log'), path.get('celery_log')]

        for logfile in logs:
            if not logfile:
                continue
            with ignoring(errno.EEXIST):
                os.mkdir(os.path.dirname(logfile))
            touch(logfile, self.log_user, self.log_group, 0o660)

    def docker_django_prepare(self):
        log.debug('Running DockerDjangoApp prepare hook')
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        aconf = self.config.get(self.app)
        uses_sqlite = aconf.get('db', {}).get('engine', '').endswith('sqlite3')
        data_dir = os.path.join(self.root, 'data')
        static_dir = self.deploy_path('collected_static')

        if uses_sqlite:
            if not os.path.exists(data_dir):
                os.mkdir(data_dir)
            chown_r(data_dir, 'www-data', 'www-data')

        if self.has_static:
            if not os.path.exists(static_dir):
                os.mkdir(static_dir)
            chown_r(static_dir, 'www-data', 'www-data')

        self.prepare_logfiles()

    def docker_django_deployed(self):
        data_dir = os.path.join(self.root, 'data')
        if os.path.exists(data_dir):
            chown_r(data_dir, 'www-data', 'www-data')


class ApacheHostedDockerDjangoApp(DockerDjangoApp, ApacheHostedApp):
    pass


class ApacheHostedDockerDjangoMultiSiteApp(
        ApacheMultiSiteApp,
        ApacheHostedDockerDjangoApp):
    pass
