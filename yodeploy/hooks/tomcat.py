import logging
import os
import platform
import subprocess
import sys

from .configurator import ConfiguratedApp
from .templating import TemplatedApp


log = logging.getLogger(__name__)

class TomcatServlet(ConfiguratedApp, TemplatedApp):
    migrate_on_deploy = False
    vhost_snippet_path = '/etc/apache2/yola.d/services'
    vhost_path = '/etc/apache2/sites-enabled'

    def prepare(self):
        super(TomcatServlet, self).prepare()
        self.prepare_tomcat()

    def prepare_tomcat(self):
        if self.migrate_on_deploy:
            self.migrate()
        if self.template_exists('apache2/vhost.conf.template'):
            self.template('apache2/vhost.conf.template',
                    os.path.join(self.vhost_path, self.app))
        if self.template_exists('apache2/vhost-snippet.conf.template'):
            if not os.path.exists(self.vhost_snippet_path):
                os.makedirs(self.vhost_snippet_path)
            self.template('apache2/vhost-snippet.conf.template',
                    os.path.join(self.vhost_snippet_path, self.app + '.conf'))

    def migrate(self):
        log.info('Running flyway migrations')
        subprocess.check_call(('java', '-cp',
            ':'.join((self.deploy_path('siteservice/WEB-INF/classes'),
                      self.deploy_path('siteservice/WEB-INF/lib/*'))),
            'com.yola.yodeploy.flywaydb.Migrator'))

    def deployed(self):
        super(TomcatServlet, self).deployed()
        self.restart_tomcat()

    def restart_tomcat(self):
        # HACK HACK HACK (thanks quicksand)
        ubuntu_version = platform.linux_distribution()[1]
        tomcat = 'tomcat7' if ubuntu_version >= '12.04' else 'tomcat6'
        try:
            subprocess.check_call(('service', 'apache2', 'reload'))
        except subprocess.CalledProcessError:
            log.exception('Unable to reload apache2')
            sys.exit(1)
        try:
            subprocess.check_call(('service', tomcat, 'try-restart'))
        except subprocess.CalledProcessError:
            log.exception('Unable to reload %s', tomcat)
            sys.exit(1)
