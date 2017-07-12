"""
Supports: supervisor, systemd, and upstart.

This looks for templates in deploy/templates/{upstart,supervisord,systemd}, and
installs them in the appropriate place for the given init system / process
manager. It then tells the manager to load, enable, and start the jobs.

The templates should be named with the disired final name + '.template', e.g.
my-celery-worker.service.template
"""

import logging
import os
import subprocess

from yodeploy.hooks.templating import TemplatedApp


log = logging.getLogger(__name__)


class Manager(object):
    name = None
    target_path = None

    def __init__(self, app):
        self.app = app
        self.installed_daemons = False

    def is_available(self):
        raise NotImplemented

    def install_daemons(self):
        for name, template, target in self.iter_templates():
            if self.app.is_daemon_enabled(name):
                log.info('Creating and restarting %s %s daemon',
                         name, self.name)
                self.app.template(template, target)
                self.reload()
                self.restart(name)
            elif os.path.exists(target):
                log.info('Removing %s %s daemon', name, self.name)
                self.destroy(name)
                os.unlink(target)
                self.reload()
            self.installed_daemons = True

    def iter_templates(self):
        if not os.path.exists(self.template_dir):
            return
        for fn in os.listdir(self.template_dir):
            if not fn.endswith('.template'):
                continue
            name = fn.split('.')[0]
            template = os.path.join(self.name, fn)
            target = os.path.join(self.target_path, fn.rsplit('.', 1)[0])
            yield name, template, target

    def reload(self):
        raise NotImplemented

    def restart(self, task):
        raise NotImplemented

    def destroy(self, task):
        raise NotImplemented

    @property
    def template_dir(self):
        return self.app.deploy_path('deploy', 'templates', self.name)


class Supervisor(Manager):
    name = 'supervisord'
    target_path = '/etc/supervisor/conf.d'

    def is_available(self):
        return os.path.exists('/usr/bin/supervisord')

    def reload(self):
        try:
            subprocess.check_call(('supervisorctl', 'reread'))
            subprocess.check_call(('supervisorctl', 'update'))
        except subprocess.CalledProcessError:
            log.error('Unable to update supervisord configs')

    def restart(self, task):
        try:
            subprocess.call(('supervisorctl', 'stop', task))
            subprocess.check_call(('supervisorctl', 'start', task))
        except subprocess.CalledProcessError:
            log.error('Unable to restart %s supervisord task', task)

    def destroy(self, task):
        subprocess.call(('supervisorctl', 'stop', task))


class SystemD(Manager):
    name = 'systemd'
    target_path = '/etc/systemd/system'

    def is_available(self):
        return os.path.exists('/bin/systemctl')

    def reload(self):
        try:
            subprocess.check_call(('systemctl', 'daemon-reload'))
        except subprocess.CalledProcessError:
            log.error('Unable to reload systemd config')

    def restart(self, task):
        try:
            subprocess.check_call(('systemctl', 'enable', task))
        except subprocess.CalledProcessError:
            log.error('Unable to install %s systemd task', task)
        try:
            subprocess.check_call(('systemctl', 'restart', task))
        except subprocess.CalledProcessError:
            log.error('Unable to restart %s systemd task', task)

    def destroy(self, task):
        try:
            subprocess.check_call(('systemctl', 'disable', task))
        except subprocess.CalledProcessError:
            log.error('Unable to uninstall %s systemd task', task)
        try:
            subprocess.check_call(('systemctl', 'stop', task))
        except subprocess.CalledProcessError:
            log.error('Unable to stop %s systemd task', task)


class Upstart(Manager):
    name = 'upstart'
    target_path = '/etc/init'

    def is_available(self):
        return os.path.exists('/sbin/initctl')

    def reload(self):
        pass

    def restart(self, task):
        try:
            subprocess.call(('service', task, 'stop'))
            subprocess.check_call(('service', task, 'start'))
        except subprocess.CalledProcessError:
            log.error('Unable to restart %s upstart task', task)

    def destroy(self, task):
        subprocess.call(('service', task, 'stop'))


class DaemonApp(TemplatedApp):
    def deployed(self):
        super(TemplatedApp, self).deployed()
        self.configure_daemons()

    def configure_daemons(self):
        supervisor = Supervisor(self)
        systemd = SystemD(self)
        upstart = Upstart(self)

        if supervisor.is_available():
            supervisor.install_daemons()

        if systemd.is_available():
            systemd.install_daemons()
        else:
            upstart.install_daemons()

        if not any(lambda service: service.installed_daemons
                   for service in (supervisor, systemd, upstart)):
            log.warning("Couldn't find any daemon templates to install for %s",
                        self.app)

    def is_daemon_enabled(self, name):
        return True
