import glob
import logging
import subprocess

from .templating import TemplatedApp


log = logging.getLogger(__name__)


class UpstartApp(TemplatedApp):
    def __init__(self, *args, **kwargs):
        super(TemplatedApp, self).__init__(*args, **kwargs)

    def deployed(self):
        super(TemplatedApp, self).deployed()
        self.configure_upstart()

    def configure_upstart(self):
        log.debug('Running UpstartApp deployed hook')
        jobs = glob.glob1(self.deploy_path('deploy', 'templates', 'upstart'),
                                          '*.template')
        if not jobs:
            log.warning('UpstartApp %s has no upstart templates', self.app)
            return

        for job in jobs:
            conf_name = job.rsplit('.', 1)[0]
            log.info('Creating and restarting %s upstart job', conf_name)
            self.template('upstart/apache2/%s' % job, '/etc/init/%s' %
                          conf_name)
            try:
                subprocess.call(('service', conf_name, 'stop'))
                subprocess.check_call(('service', conf_name, 'start'))
            except subprocess.CalledProcessError:
                log.error('Unable to restart %s worker', conf_name)
