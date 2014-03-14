from os.path import basename
import glob
import logging
import subprocess

from yodeploy.hooks.templating import TemplatedApp


log = logging.getLogger(__name__)


class SupervisordApp(TemplatedApp):
    """ This looks for *.conf.template jobs in deploy/templates/supervisord
        and sticks them in /etc/supervisor/conf.d/{job}.conf

        It then calls supervisorctl reread and supervisorctl update.
        reread: reloads the job configurations in /etc/supervisor/conf.d/
        update: applys any changes to currently running jobs."""

    def __init__(self, *args, **kwargs):
        super(TemplatedApp, self).__init__(*args, **kwargs)

    def deployed(self):
        super(TemplatedApp, self).deployed()
        self.configure_supervisord()

    def configure_supervisord(self):
        log.debug('Running SupervisordApp deployed hook')
        jobs = [basename(job) for job
                in glob.glob(self.deploy_path('deploy', 'templates',
                                              'supervisord', '*.template'))]
        if not jobs:
            log.warning('SupervisordApp %s has no supervisord templates',
                        self.app)
            return

        for job in jobs:
            conf_name = job.rsplit('.', 1)[0]
            job_name = conf_name.rsplit('.', 1)[0]
            log.info('Creating and restarting %s supervisord job', conf_name)
            self.template('supervisord/%s' % job, '/etc/supervisor/conf.d/%s' %
                          conf_name)
            try:
                subprocess.check_call(('supervisorctl', 'reread'))
                subprocess.check_call(('supervisorctl', 'update'))
            except subprocess.CalledProcessError:
                log.error('Unable to update supervisord configs')

            try:
                subprocess.call(('supervisorctl', 'stop', job_name))
                subprocess.check_call(('supervisorctl', 'start', job_name))
            except subprocess.CalledProcessError:
                log.error('Unable to restart %s supervisord job', conf_name)
