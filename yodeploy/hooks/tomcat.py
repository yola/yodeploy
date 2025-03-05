import logging
import os
import pwd
import shutil
import subprocess
import sys
import time
from pathlib import Path
import distro

from yodeploy.hooks.configurator import ConfiguratedApp


log = logging.getLogger(__name__)


class TomcatServlet(ConfiguratedApp):
    migrate_on_deploy = False
    vhost_path = '/etc/apache2/sites-enabled'
    parallel_deploy_timeout = 60
    database_migration_class = 'com.yola.yodeploy.flywaydb.Migrator'

    def prepare(self):
        super(TomcatServlet, self).prepare()
        self.prepare_tomcat()

    def prepare_tomcat(self):
        if self.migrate_on_deploy:
            self.migrate()
        if self.has_apache_vhost:
            dest = os.path.join(self.vhost_path, '%s.conf' % self.app)
            self.template('apache2/vhost.conf.template', dest)

        # clean up old vhosts, yodeploy <= v0.7.3 did not append `.conf`
        old_vhost = os.path.join(self.vhost_path, self.app)
        if os.path.exists(old_vhost):
            os.unlink(old_vhost)

    @property
    def has_apache_vhost(self):
        return self.template_exists('apache2/vhost.conf.template')

    def migrate(self):
        log.info('Running flyway migrations')
        subprocess.check_call((
            'java', '-cp',
            ':'.join((self.deploy_path('%s/WEB-INF/classes' % self.app),
                      self.deploy_path('%s/WEB-INF/lib/*' % self.app))),
            self.database_migration_class))

    def deployed(self):
        super(TomcatServlet, self).deployed()
        self.tomcat_deploy()

    def tomcat_deploy(self):
        if self.has_apache_vhost:
            try:
                subprocess.check_call(('service', 'apache2', 'reload'))
            except subprocess.CalledProcessError:
                log.exception('Unable to reload apache2')
                sys.exit(1)

        contexts = os.path.join(self.root, 'tomcat-contexts')
        if not os.path.isdir(contexts):
            os.mkdir(contexts)

        # Tomcat does string comparisons.
        # Versions aren't strictly numeric, local builds will have a .n
        # appended. So:
        # 10   -> 0000000010
        # 10.1 -> 0000000010.0000000001
        version = f'{self.version:10}'.partition('.')
        version = f'{version[0]:0>10}{version[1]}{version[2]:0>10}'.rstrip()

        deployed = self._deployed_versions()

        previously_deployed = set(deployed)
        if not previously_deployed:
            # Give the initial deploy an artificially low version, so it will
            # be replaced by the first local build in an integration
            # environment.
            version = '0' * 10

        redeploys = sorted(name for name in deployed
                           if name.startswith(version))
        if redeploys:
            latest = redeploys[-1]
            if latest == version:
                redeploy = 0
            else:
                redeploy = int(latest.rsplit('.', 1)[1]) + 1
            version = f'{version}.{redeploy:010d}'

        dest = Path(os.path.join(contexts, 'ROOT##%s' % version))

        ubuntu_version = distro.version()
        tomcat = 'tomcat9' if ubuntu_version >= '20.04' else 'tomcat8'
        uid = pwd.getpwnam(tomcat).pw_uid

        os.chown(contexts, uid, -1)

        # Build a hard linkfarm in the tomcat-contexts directory.
        # Copy the configuration XML files, so that tomcat sees that they are
        # inside appBase and can delete them.
        self._linkfarm(
            self.deploy_path(self.app),
            dest,
            uid,
            (self.deploy_path(self.app, 'META-INF'),
             self.deploy_path(self.app, 'WEB-INF'))
        )

        # Put configuration.json somewhere where yodeploy-java can find it.
        config_src = Path(self.deploy_path('configuration.json'))
        config_dst = dest / 'configuration.json'
        config_dst.unlink(missing_ok=True)
        config_dst.symlink_to(config_src)

        # Drop down the XML files last, to trigger the Tomcat deploy
        for metadir in ('META-INF', 'WEB-INF'):
            src_path = Path(self.deploy_path(self.app, metadir))
            dst_path = dest / metadir
            for src in src_path.glob('*.xml'):
                dst = dst_path / src.name
                shutil.copyfile(src, dst)
                os.chown(dst, uid, -1)

        if not previously_deployed:
            log.info('No existing versions, assuming we have successfully '
                     'deployed')
            return

        log.info('Waiting %is for tomcat to deploy the new version (%s), '
                 'and clean up an old one...',
                 self.parallel_deploy_timeout, version)
        for i in range(self.parallel_deploy_timeout):
            deployed = set(self._deployed_versions())
            if len(previously_deployed - deployed) >= 1:
                break
            time.sleep(1)
        else:
            raise Exception("Deploy must have failed - "
                            "tomcat didn't undeploy any old verisons")

    def _deployed_versions(self):
        contexts = os.path.join(self.root, 'tomcat-contexts')
        return [name.split('##', 1)[1] for name in os.listdir(contexts)
                if '##' in name]

    def _linkfarm(self, srcdir, dstdir, uid, metadirs):
        src_path = Path(srcdir)
        dst_path = Path(dstdir)
        dst_path.mkdir()
        os.chown(dst_path, uid, -1)

        for src in src_path.iterdir():
            if srcdir in metadirs and src.suffix == '.xml':
                continue
            dst = dst_path / src.name
            if src.is_dir():
                self._linkfarm(src, dst, uid, metadirs)
            else:
                os.link(src, dst)
                os.chown(dst, uid, -1)
