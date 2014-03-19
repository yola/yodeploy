from os.path import basename
import glob
import logging
import subprocess

from yodeploy.hooks.templating import TemplatedApp


log = logging.getLogger(__name__)


class UpstartApp(TemplatedApp):
    def __init__(self, *args, **kwargs):
        super(TemplatedApp, self).__init__(*args, **kwargs)

    def deployed(self):
        super(TemplatedApp, self).deployed()
        self.configure_upstart()

    def configure_upstart(self):
        log.debug('Running UpstartApp deployed hook')
        jobs = [basename(job) for job
                in glob.glob(self.deploy_path('deploy', 'templates', 'upstart',
                                              '*.template'))]
        if not jobs:
            log.warning('UpstartApp %s has no upstart templates', self.app)
            return

        for job in jobs:
            conf_name = job.rsplit('.', 1)[0]
            job_name = conf_name.rsplit('.', 1)[0]
            log.info('Creating and restarting %s upstart job', conf_name)
            self.template('upstart/%s' % job, '/etc/init/%s' %
                          conf_name)
            try:
                subprocess.call(('service', job_name, 'stop'))
                subprocess.check_call(('service', job_name, 'start'))
            except subprocess.CalledProcessError:
                log.error('Unable to restart %s upstart job', conf_name)
