import logging
import os

import tempita

from yodeploy.hooks.base import DeployHook


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
                                 cconf=self.config.get('common', {}))
        with open(destination, 'w') as f:
            f.write(output)

        os.chmod(destination, perm)

    def template_all(self, path, dest):
        """Write all templates in the path to the destination.

        Returns the number of templates processed.
        """
        count = 0
        if not self.template_exists(path):
            return count
        template_path = self.template_filename(path)
        for tmpl in os.listdir(template_path):
            self.template(os.path.join(path, tmpl), os.path.join(dest, tmpl))
            count += 1
        return count
