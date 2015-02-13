"""Application hooks for apps that use Apache."""

import logging
import os
import subprocess
import sys

from os.path import join

from yodeploy.hooks.configurator import ConfiguratedApp

log = logging.getLogger(__name__)


class Apache(object):

    @staticmethod
    def reload():
        try:
            subprocess.check_call(('service', 'apache2', 'reload'))
        except subprocess.CalledProcessError:
            log.error("Unable to reload apache2.")
            sys.exit(1)


class ApacheHostedApp(ConfiguratedApp):
    vhost_path = '/etc/apache2/sites-enabled'
    includes_path = '/etc/apache2/yola.d'
    apache = Apache

    def deployed(self):
        super(ApacheHostedApp, self).deployed()
        self.apache_hosted_deployed()

    def prepare(self):
        super(ApacheHostedApp, self).prepare()
        self.apache_hosted_prepare()

    def apache_hosted_prepare(self):
        """Create a vhost and place optional includes."""
        log.debug("Running ApacheHostedApp prepare hook.")
        self.place_vhost()
        self.place_includes()

    def place_vhost(self):
        dest = join(self.vhost_path, "%s.conf" % self.app)
        self.template('apache2/vhost.conf.template', dest)

        # clean up old vhosts, yodeploy <= v0.4.24 did not append `.conf`
        old_vhost = join(self.vhost_path, self.app)
        if os.path.exists(old_vhost):
            os.unlink(old_vhost)

    def place_includes(self):
        """Place all snippits in Apache's yola.d.

        Create an appname sub-folder to house the snippits.
        """
        yolad_app_path = join(self.includes_path, self.app)
        tmpls_dir = join('apache2', 'yola.d', self.app)
        self.template_all(tmpls_dir, yolad_app_path)

    def apache_hosted_deployed(self):
        self.apache.reload()


class ApacheMultiSiteApp(ApacheHostedApp):

    def apache_hosted_prepare(self):
        """Create a several vhosts and place optional includes."""
        log.debug("Running ApacheMultiSiteApp prepare hook.")
        self.place_vhosts()
        self.place_includes()

    def place_vhosts(self):
        tmpl_dir = join('apache2', 'sites')
        self.template_all(tmpl_dir, self.vhost_path, min_count=2)
