import logging
import os
import subprocess

from yola.deploy.util import chown_r
from .configurator import ConfiguratedApp
from .python import PythonApp
from .templating import TemplatedApp


log = logging.getLogger(__name__)


class DjangoApp(ConfiguratedApp, PythonApp, TemplatedApp):
    def __init__(self, *args, **kwargs):
        super(ConfiguratedApp, self).__init__(*args, **kwargs)
        self.migrate_on_deploy = False
        self.uses_south = False

    def prepare(self):
        super(DjangoApp, self).prepare()
        self.django_prepare()

    def django_prepare(self):
        log.debug('Running DjangoApp prepare hook')
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        app_dir = os.path.join(self.root, 'versions', self.version)
        if self.template_exists('apache2/vhost.conf.template'):
            self.template('apache2/vhost.conf.template',
                    os.path.join('/etc/apache2/sites-enabled', self.app))
        if self.template_exists('apache2/wsgi-handler.wsgi.template'):
            self.template('apache2/wsgi-handler.wsgi.template',
                          os.path.join(app_dir, self.app + '.wsgi'))

        if self.migrate_on_deploy:
            self.migrate()

        self.manage_py('collectstatic', '--noinput')

    def migrate(self):
        log.info('Running migrations on %s', self.app)
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        app_dir = os.path.join(self.root, 'versions', self.version)
        data_dir = os.path.join(self.root, 'data')
        uses_sqlite = self.config.db.engine.endswith('sqlite3')
        new_db = False
        if uses_sqlite:
            if not os.path.exists(data_dir):
                new_db = True
                os.mkdir(data_dir)

        self.manage_py('syncdb', '--noinput')
        if self.uses_south:
            self.manage_py('migrate')

        if new_db:
            seed_data = os.path.join(app_dir, 'seed_data.json')
            if os.path.exists(seed_data):
                self.manage_py('loaddata', seed_data)

        if os.path.exists(data_dir):
            chown_r(data_dir, 'www-data', 'www-data')

    def manage_py(self, command, *args):
        app_dir = os.path.join(self.root, 'versions', self.version)
        subprocess.check_call([
            os.path.join(app_dir, 'virtualenv', 'bin/python'),
            os.path.join(app_dir, 'manage.py'),
            command] + list(args))
