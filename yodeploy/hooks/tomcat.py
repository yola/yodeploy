import logging
import platform
import subprocess
import sys

from yodeploy.hooks.configurator import ConfiguratedApp


log = logging.getLogger(__name__)

class TomcatServlet(ConfiguratedApp):
    migrate_on_deploy = False

    def prepare(self):
        super(TomcatServlet, self).prepare()
        if self.migrate_on_deploy:
            self.migrate()

    def migrate(self):
        log.info('Running flyway migrations')
        subprocess.check_call(('java', '-cp',
            ':'.join((self.deploy_path('siteservice/WEB-INF/classes'),
                      self.deploy_path('siteservice/WEB-INF/lib/*'))),
            'com.yola.yodeploy.flywaydb.Migrator'))

    def deployed(self):
        super(Hooks, self).deployed()
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
