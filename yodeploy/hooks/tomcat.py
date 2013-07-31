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
            ':'.join((self.deploy_path('%s/WEB-INF/classes' % self.app),
                      self.deploy_path('%s/WEB-INF/lib/*' % self.app))),
            'com.yola.yodeploy.flywaydb.Migrator'))

    def deployed(self):
        super(TomcatServlet, self).deployed()
        self.tomcat_deploy()

    def tomcat_deploy(self):
        try:
            subprocess.check_call(('service', 'apache2', 'reload'))
        except subprocess.CalledProcessError:
            log.exception('Unable to reload apache2')
            sys.exit(1)

        contexts = os.path.join(self.root, 'tomcat-contexts')
        if not os.path.isdir(contexts):
            os.mkdir(contexts)

        ubuntu_version = platform.linux_distribution()[1]
        tomcat = 'tomcat7' if ubuntu_version >= '12.04' else 'tomcat6'
        if tomcat == 'tomcat6':
            dest = os.path.join(contexts, 'ROOT')
            if os.path.exists(dest):
                os.unlink(dest)
        else:
            # Tomcat does string comparisons.
            # Versions aren't strictly numeric, local builds will have a .n
            # appended. So:
            # 10   -> 0000000010
            # 10.1 -> 0000000010.0000000001
            version = '%10s%s%10s' % self.version.partition('.')
            version = version.rstrip().replace(' ', '0')
            dest = os.path.join(contexts, 'ROOT##%s' % version)
        os.symlink(self.deploy_path(self.app), dest)
