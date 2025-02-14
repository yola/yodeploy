import crypt
import logging
import os
import random

from yoconfigurator.credentials import seeded_auth_token

from yodeploy.hooks.configurator import ConfiguratedApp


log = logging.getLogger(__name__)


def salt():
    salt_chars = ('0123456789./'
                  'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                  'abcdefghijklmnopqrstuvwxyz')
    return '$6$%s' % ''.join(random.choice(salt_chars) for i in range(16))


class AuthenticatedApp(ConfiguratedApp):
    """A deploy hook that writes an htpasswd file for the app.

    Users and clients can be specified in the application configuration, for
    example, in `appname/deploy/configuration/appname-default.py`:

        from yoconfigurator.dicts import merge_dicts

        def update(config):

            appname_config = {
                'appname': {
                    'htpasswd': {
                        'clients': ['myyola', 'sitebuilder', 'yolacom'],
                        'users': {'yoladmin': 'password'},
                        'groups': {'group1': ['client1', 'client2']},
                    }
                }
            }

            return merge_dicts(config, appname_config)

    Client passwords are automatically configured using the client name, app
    name, and api seed from deployconfigs.

    The file will be written to `/etc/yola/httpasswd/appname`. You can
    configure your app's auth in its apache template. For example, in
    `appname/deploy/templates/apache2/vhost.conf.template`:

        <VirtualHost *:80>
            # ...other vhosty stuff...
            <Location />
                AuthType Basic
                AuthName "appname"
                AuthUserFile /etc/yola/htpasswd/appname
                Require valid-user
            </Location>
        </VirtualHost>

    To create a separate htpasswd file for certain group of clients one can
    include it in 'groups' in application's 'htpasswd' configuration.
    This will result in /etc/yola/httpasswd/appname_<GROUP_NAME> file creation.
    """

    HTPASSWD_DIR = '/etc/yola/htpasswd'

    def prepare(self):
        super(AuthenticatedApp, self).prepare()
        self.auth_prepare()

    def auth_prepare(self):
        log.debug('Running AuthenticatedApp prepare hook')
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        if not os.path.exists(self.HTPASSWD_DIR):
            os.makedirs(self.HTPASSWD_DIR)

        htpasswd_fn = os.path.join(self.HTPASSWD_DIR, self.app)
        htpasswd_conf = self.config.get(self.app).htpasswd
        with open(htpasswd_fn, 'w') as f:
            for user, password in htpasswd_conf.get('users', {}).items():
                f.write('{0}:{1}\n'.format(
                    user, crypt.crypt(password, salt())))

            for client_name in htpasswd_conf.get('clients', []):
                self._write_seeded_htpasswd_entry(f, client_name)

        for group_name, clients in htpasswd_conf.get('groups', {}).items():
            file_name = '{0}_{1}'.format(htpasswd_fn, group_name)
            with open(file_name, 'w') as f:
                for client_name in clients:
                    self._write_seeded_htpasswd_entry(f, client_name)

    def _write_seeded_htpasswd_entry(self, fh, client_name):
        password = seeded_auth_token(
            client_name, self.app, self.config.common.api_seed)
        crypted = crypt.crypt(password, salt())
        fh.write('{0}:{1}\n'.format(client_name, crypted))
