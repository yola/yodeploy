import logging
import os
import subprocess

from yola.deploy.util import chown_r, touch
from .configurator import ConfiguratedApp
from .python import PythonApp
from .templating import TemplatedApp


log = logging.getLogger(__name__)


class DjangoApp(ConfiguratedApp, PythonApp, TemplatedApp):
    migrate_on_deploy = False
    uses_south = False

    def __init__(self, *args, **kwargs):
        super(ConfiguratedApp, self).__init__(*args, **kwargs)

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

        app_dir = os.path.join(self.root, 'versions', self.version)
        if self.template_exists('apache2/vhost.conf.template'):
            self.template('apache2/vhost.conf.template',
                    os.path.join('/etc/apache2/sites-enabled', self.app))
        if self.template_exists('apache2/wsgi-handler.wsgi.template'):
            self.template('apache2/wsgi-handler.wsgi.template',
                          os.path.join(app_dir, self.app + '.wsgi'))

        if self.migrate_on_deploy:
            self.migrate()

        logfile = self.config.get(self.app, {}).get('path', {}).get('log',
                                                                    None)
        if logfile:
            touch(logfile, 'www-data', 'adm', 0640)

        self.manage_py('collectstatic', '--noinput')

    def django_deployed(self):
        subprocess.check_call(('service', 'apache2', 'reload'))

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
        cmd = ['virtualenv/bin/python', 'manage.py', command] + list(args)
        log.debug("Executing %r", cmd)
        subprocess.check_call(cmd, cwd=app_dir)
