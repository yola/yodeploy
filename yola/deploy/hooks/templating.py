import logging
import os

import tempita

from .base import DeployHook


log = logging.getLogger(__name__)


class TemplatedApp(DeployHook):
    def template_exists(self, template_name):
        app_dir = os.path.join(self.app, 'versions', self.version)
        fn = os.path.join(app_dir, 'deploy', 'templates')
        return os.path.exists(fn)

    def template(self, template_name, destination):
        log.debug('Parsing template: %s -> %s', template_name, destination)
        app_dir = os.path.join(self.app, 'versions', self.version)
        fn = os.path.join(app_dir, 'deploy', 'templates')
        tmpl = tempita.Template.from_filename(fn)

        output = tmpl.substitute(self.config)
        with open(destination, 'w') as f:
            f.write(output)
