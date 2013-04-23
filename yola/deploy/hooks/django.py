import logging
import os
import subprocess
import sys

from yola.deploy.util import chown_r, touch
from .configurator import ConfiguratedApp
from .python import PythonApp
from .templating import TemplatedApp


log = logging.getLogger(__name__)


class DjangoApp(ConfiguratedApp, PythonApp, TemplatedApp):
    migrate_on_deploy = False
    uses_south = False
    has_media = False
    compress = False
    compile_i18n = False
    has_static = False
    vhost_path = '/etc/apache2/sites-enabled'
    vhost_snippet_path = '/etc/apache2/yola.d/services'

    def __init__(self, *args, **kwargs):
        super(DjangoApp, self).__init__(*args, **kwargs)

    def prepare(self):
        super(DjangoApp, self).prepare()
        self.django_prepare()

    def deployed(self):
        super(DjangoApp, self).deployed()
        self.django_deployed()

    def django_prepare(self):
        log.debug('Running DjangoApp prepare hook')
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        if self.template_exists('apache2/vhost.conf.template'):
            self.template('apache2/vhost.conf.template',
                    os.path.join(self.vhost_path, self.app))
        if self.template_exists('apache2/vhost-snippet.conf.template'):
            if not os.path.exists(vhost_snippet_path):
                os.mkdirs(vhost_snippet_path)
            self.template('apache2/vhost-snippet.conf.template',
                    os.path.join(self.vhost_snippet_path, self.app + '.conf'))
        if self.template_exists('apache2/wsgi-handler.wsgi.template'):
            self.template('apache2/wsgi-handler.wsgi.template',
                          self.deploy_path(self.app + '.wsgi'))

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

        if self.migrate_on_deploy:
            self.migrate()

        logfile = self.config.get(self.app, {}).get('path', {}).get('log',
                                                                    None)
        if logfile:
            touch(logfile, 'www-data', 'adm', 0640)

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
        try:
            subprocess.check_call(('service', 'apache2', 'reload'))
        except subprocess.CalledProcessError:
            log.error("Unable to reload apache2")
            sys.exit(1)

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
