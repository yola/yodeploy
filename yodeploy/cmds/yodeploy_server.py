import argparse
import logging
import os
import sys

from gunicorn.app.base import BaseApplication

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from yodeploy.config import find_deploy_config
from yodeploy.deploy import configure_logging
from yodeploy.flask_app.app import create_app

log = logging.getLogger('yodeploy')


class YodeployApplication(BaseApplication):
    def __init__(self):
        self.application = create_app(find_deploy_config())
        super(YodeployApplication, self).__init__()

    def load_config(self):
        config = self.application.config
        parser = argparse.ArgumentParser(description='Yodeploy server')

        parser.add_argument('--listen', '-l', help='Bind to this IP address',
                            default='0.0.0.0')
        parser.add_argument('--port', '-p', type=int,
                            default=config.server.port,
                            help='Port to listen on (default: %s)'
                                 % config.server.port)
        parser.add_argument('--debug', '-d', action='store_true',
                            help='Increase verbosity')

        opts = parser.parse_args()

        configure_logging(opts.debug, config.server.logging)

        self.cfg.set('bind', '{}:{}'.format(opts.listen, opts.port))
        self.cfg.set('ciphers', config.server.ssl.ciphers)
        self.cfg.set('ssl_version', config.server.ssl.ssl_version)
        self.cfg.set('certfile', config.server.ssl.cert_chain)
        self.cfg.set('keyfile', config.server.ssl.key)
        self.cfg.set('workers', config.server.workers)

    def load(self):
        return self.application


if __name__ == '__main__':
    YodeployApplication().run()
