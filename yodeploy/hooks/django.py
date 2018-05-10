import errno
import logging
import os
import subprocess
import sys

from pkg_resources import parse_version

from yodeploy.hooks.apache import ApacheHostedApp, ApacheMultiSiteApp
from yodeploy.hooks.configurator import ConfiguratedApp
from yodeploy.hooks.nginx import NginxHostedApp
from yodeploy.hooks.python import PythonApp
from yodeploy.util import chown_r, ignoring, touch


log = logging.getLogger(__name__)


class DjangoApp(ConfiguratedApp, PythonApp):
    migrate_on_deploy = False
    has_migrations = False
    has_media = False
    compress = False
    compile_i18n = False
    has_static = False
    log_user = 'www-data'
    log_group = 'adm'

    def prepare(self):
        super(DjangoApp, self).prepare()
        self.django_prepare()

    def deployed(self):
        self.django_deployed()
        super(DjangoApp, self).deployed()

    def prepare_logfiles(self):
        path = self.config.get(self.app, {}).get('path', {})
        logs = [path.get('log'), path.get('celery_log')]

        for logfile in logs:
            if not logfile:
                continue
            with ignoring(errno.EEXIST):
                os.mkdir(os.path.dirname(logfile))
            touch(logfile, self.log_user, self.log_group, 0o640)

    def call_compress(self):
        if not self.compress:
            return

        file_exts_to_compress = [] if self.compress is True else self.compress
        cmd = ['compress', '--force']
        [cmd.extend(('-e', ext)) for ext in file_exts_to_compress]

        self.manage_py(*cmd)

    def django_prepare(self):
        log.debug('Running DjangoApp prepare hook')
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        aconf = self.config.get(self.app)
        uses_sqlite = aconf.get('db', {}).get('engine', '').endswith('sqlite3')
        data_dir = os.path.join(self.root, 'data')
        media_dir = os.path.join(self.root, 'data', 'media')

        if uses_sqlite or self.has_media:
            if not os.path.exists(data_dir):
                os.mkdir(data_dir)
            if self.has_media and not os.path.exists(media_dir):
                os.mkdir(media_dir)
            chown_r(data_dir, 'www-data', 'www-data')

        self.prepare_logfiles()

        if self.migrate_on_deploy:
            self.migrate()

        if self.has_static:
            self.manage_py('collectstatic', '--noinput')

        self.call_compress()

        if self.compile_i18n:
            self.manage_py('compilemessages')

    def django_deployed(self):
        data_dir = os.path.join(self.root, 'data')
        if os.path.exists(data_dir):
            chown_r(data_dir, 'www-data', 'www-data')

    @property
    def django_version(self):
        return parse_version(self.manage_py('version'))

    def run_migrate_commands(self):
        if self.django_version >= parse_version('1.7.0'):
            self.manage_py('migrate', '--noinput')
        else:
            self.manage_py('syncdb', '--noinput')
            if self.has_migrations:
                self.manage_py('migrate')

    def migrate(self):
        log.info('Running migrations on %s', self.app)
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        data_dir = os.path.join(self.root, 'data')
        aconf = self.config.get(self.app)

        if 'db' not in aconf:
            return

        uses_sqlite = aconf.db.engine.endswith('sqlite3')
        new_db = False
        if uses_sqlite:
            if not os.path.exists(aconf.db.name):
                new_db = True

        self.run_migrate_commands()

        if new_db:
            seed_data = self.deploy_path(self.app, 'seed_data.json')
            if os.path.exists(seed_data):
                self.manage_py('loaddata', seed_data)

        if os.path.exists(data_dir):
            chown_r(data_dir, 'www-data', 'www-data')

    def manage_py(self, command, *args):
        cmd = ['virtualenv/bin/python',
               os.path.join(self.app, 'manage.py'),
               command] + list(args)
        log.debug("Executing %r", cmd)
        try:
            output = subprocess.check_output(cmd, cwd=self.deploy_dir)
        except subprocess.CalledProcessError:
            log.error("Management command failed: %r", [command] + list(args))
            sys.exit(1)
        return output.decode('utf-8')


class ApacheHostedDjangoApp(DjangoApp, ApacheHostedApp):
    pass


class ApacheHostedDjangoMultiSiteApp(
        ApacheMultiSiteApp,
        ApacheHostedDjangoApp):

    pass


class NginxHostedDjangoApp(DjangoApp, NginxHostedApp):
    pass
