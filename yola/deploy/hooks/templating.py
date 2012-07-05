import logging
import os

import tempita

from .base import DeployHook


log = logging.getLogger(__name__)


class TemplatedApp(DeployHook):
    def template_filename(self, template_name):
        return self.deploy_path('deploy', 'templates', template_name)

    def template_exists(self, template_name):
        return os.path.exists(self.template_filename(template_name))

    def template(self, template_name, destination, perm=0644):
        log.debug('Parsing template: %s -> %s', template_name, destination)
        fn = self.template_filename(template_name)
        tmpl = tempita.Template.from_filename(fn)

        output = tmpl.substitute(conf=self.config,
                                 aconf=self.config.get(self.app, {}),
                                 gconf=self.config.get('global', {}))
        with open(destination, 'w') as f:
            f.write(output)

        os.chmod(destination, perm)
