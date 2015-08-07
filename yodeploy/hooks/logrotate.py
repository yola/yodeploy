from yodeploy.hooks.templating import TemplatedApp

import logging
import os
import tempita

log = logging.getLogger(__name__)
LOGROTATE_DIR = '/etc/logrotate.d'
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), 'templates')


class LogrotateApp(TemplatedApp):
    def __init__(self, *args, **kwargs):
        super(LogrotateApp, self).__init__(*args, **kwargs)
        self.logs = []

    def add_log(self, path, frequency='daily', rotate=14,
                create='0644 root adm', size=None, options=None,
                sharedscripts=None, postrotate=None, prerotate=None,
                firstaction=None, lastaction=None):
        if options is None:
            options = []
        self.logs.append({
            'path': path,
            'frequency': frequency,
            'rotate': rotate,
            'create': create,
            'size': size,
            'options': options,
            'sharedscripts': sharedscripts,
            'postrotate': postrotate,
            'prerotate': prerotate,
            'firstaction': firstaction,
            'lastaction': lastaction
        })

    def template_filename(
            self, template_name=os.path.join(TEMPLATE_PATH, 'logrotate')):
        return super(template_name)

    def deployed(self):
        super(TemplatedApp, self).deployed()
        self.configure_logrotate()

    def configure_logrotate(self):
        log.debug('Running Logrotate deployed hook')
        fn = self.template_filename()
        tmpl = tempita.Template.from_filename(fn)
        output = tmpl.substitute(logfiles=self.logs)
        destination = os.path.join(LOGROTATE_DIR, self.app)
        with open(destination, 'w') as f:
            f.write(output)
        os.chmod(destination, 0644)


