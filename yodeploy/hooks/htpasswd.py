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
                        'groupname_users': {'user1': 'password'},
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

    To create a separate htpasswd file for certain group of users one can
    include '<GROUP_NAME>_users' in application's 'htpasswd' configuration.
    This will result in /etc/yola/httpasswd/appname_<GROUP_NAME> file creation.
    """

    HTPASSWD_DIR = '/etc/yola/htpasswd'

    def __init__(self, *args, **kwargs):
        super(AuthenticatedApp, self).__init__(*args, **kwargs)

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
        aconf = self.config.get(self.app)
        with open(htpasswd_fn, 'w') as f:
            if 'users' in aconf.htpasswd:
                self._write_credentials_to_file(f, aconf.htpasswd.users)

            if 'clients' in aconf.htpasswd:
                for client in aconf.htpasswd.clients:
                    password = seeded_auth_token(
                        client, self.app, self.config.common.api_seed)
                    crypted = crypt.crypt(password, salt())
                    f.write('%s:%s\n' % (client, crypted))

        for section_name, credentials in aconf.htpasswd.iteritems():
            if section_name.endswith('_users'):
                group_name = section_name.rsplit('_', 1)[0]
                file_name = '{0}_{1}'.format(htpasswd_fn, group_name)
                with open(file_name, 'w') as f:
                    self._write_credentials_to_file(f, credentials)

    def _write_credentials_to_file(self, fh, users):
        for user, password in users.iteritems():
            fh.write('%s:%s\n' % (user, crypt.crypt(password, salt())))
