import errno
import logging
import os
import subprocess
import sys

from yodeploy.hooks.apache import ApacheHostedApp, ApacheMultiSiteApp
from yodeploy.hooks.configurator import ConfiguratedApp
from yodeploy.hooks.python import PythonApp
from yodeploy.util import chown_r, touch


log = logging.getLogger(__name__)

class DjangoApp(ApacheHostedApp, PythonApp):
    migrate_on_deploy = False
    uses_south = False
    has_media = False
    compress = False
    compile_i18n = False
    has_static = False
    vhost_path = '/etc/apache2/sites-enabled'
    vhost_snippet_path = '/etc/apache2/yola.d/services'

    def prepare(self):
        super(DjangoApp, self).prepare()
        self.django_prepare()

    def deployed(self):
        self.django_deployed()
        super(DjangoApp, self).deployed()

    def place_wsgi_handler(self):
        if not self.template_exists('apache2/wsgi-handler.wsgi.template'):
            raise Exception(
                "The DjangoApp is missing a template for the wsgi handler.")
        self.template(
            'apache2/wsgi-handler.wsgi.template',
            self.deploy_path(self.app + '.wsgi'))

    def django_prepare(self):
        log.debug('Running DjangoApp prepare hook')
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        self.place_wsgi_handler()

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

        logfile = self.config.get(self.app, {}).get('path', {}).get('log',
                                                                    None)
        if logfile:
            try:
                os.mkdir(os.path.dirname(logfile))
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise

            touch(logfile, 'www-data', 'adm', 0640)

        if self.migrate_on_deploy:
            self.migrate()

        if self.has_static:
            self.manage_py('collectstatic', '--noinput')

        if self.compress:
            cmd = ['compress', '--force']
            if isinstance(self.compress, list):
                for extension in self.compress:
                    cmd += ['-e', extension]
            self.manage_py(*cmd)

        if self.compile_i18n:
            self.manage_py('compilemessages')

    def django_deployed(self):
        data_dir = os.path.join(self.root, 'data')
        if os.path.exists(data_dir):
            chown_r(data_dir, 'www-data', 'www-data')

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

        self.manage_py('syncdb', '--noinput')
        if self.uses_south:
            self.manage_py('migrate')

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
            subprocess.check_call(cmd, cwd=self.deploy_dir)
        except subprocess.CalledProcessError:
            log.error("Management command failed: %r", [command] + list(args))
            sys.exit(1)


class DjangoMultiSiteApp(ApacheMultiSiteApp, DjangoApp):

    pass
