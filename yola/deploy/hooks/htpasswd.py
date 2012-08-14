import crypt
import logging
import os
import random

from yola.configurator.credentials import seeded_auth_token
from .configurator import ConfiguratedApp


log = logging.getLogger(__name__)


def salt():
    salt_chars = ('0123456789./'
                  'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                  'abcdefghijklmnopqrstuvwxyz')
    return '$6$%s' % ''.join(random.choice(salt_chars) for i in range(16))


class AuthenticatedApp(ConfiguratedApp):
    def __init__(self, *args, **kwargs):
        super(AuthenticatedApp, self).__init__(*args, **kwargs)

    def prepare(self):
        super(AuthenticatedApp, self).prepare()
        self.auth_prepare()

    def app_prepare(self):
        log.debug('Running AuthenticatedApp prepare hook')
        if self.config is None:
            raise Exception("Config hasn't been loaded yet")

        if not os.path.exists('/etc/yola/htpasswd'):
            os.makedirs('/etc/yola/htpasswd')
        htpasswd_fn = os.path.join('/etc/yola/htpasswd', self.app)
        aconf = self.config.get(self.app)
        with open(htpasswd_fn, 'w') as f:
            if 'users' in aconf.htpasswd:
                for user, password in aconf.htpasswd.users.iteritems():
                    f.write('%s: %s\n' % (user, crypt.crypt(password, salt())))

            if 'clients' in aconf.htpasswd:
                for client in aconf.htpasswd.clients:
                    password = seeded_auth_token(client, self.app,
                            self.config.common.credential.api_seed)
                    crypted = crypt.crypt(password, salt())
                    f.write('%s: %s\n' % (client, crypted))
