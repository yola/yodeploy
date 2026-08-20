import logging
import os
import subprocess
import sys

from yodeploy.hooks.configurator import ConfiguratedApp


log = logging.getLogger(__name__)


class PrismaApp(ConfiguratedApp):
    migrate_on_deploy = False

    def prepare(self):
        super(PrismaApp, self).prepare()
        self.prisma_prepare()

    def prisma_prepare(self):
        log.info('Running PrismaApp prepare hook')
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")
        if self.migrate_on_deploy:
            self.migrate()

    def migrate(self):
        log.info('Running migrations on %s', self.app)
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        aconf = self.config.get(self.app)

        if 'db' not in aconf:
            return

        self.prisma_command('migrate', 'deploy')

    def prisma_command(self, command, *args):
        app_dir = self.deploy_path(self.app)
        cmd = [
            'node',
            os.path.join(app_dir, 'node_modules', '.bin', 'prisma'),
            command,
        ] + list(args)
        log.debug("Executing %r", cmd)
        try:
            output = subprocess.check_output(cmd, cwd=app_dir)
        except subprocess.CalledProcessError:
            log.error("Prisma command failed: %r", cmd, exc_info=True)
            sys.exit(1)
        return output.decode('utf-8')
