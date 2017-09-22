import argparse
import logging
import os
import ssl
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from yodeploy.config import find_deploy_config
from yodeploy.deploy import configure_logging
from yodeploy.flask_app.app import create_app

log = logging.getLogger('yodeploy')


def parse_args(flask_app):
    parser = argparse.ArgumentParser(description='Yodeploy server')

    parser.add_argument('--listen', '-l', help='Bind to this IP address',
                        default='0.0.0.0')
    parser.add_argument('--port', '-p', type=int,
                        default=flask_app.config.server.port,
                        help='Port to listen on (default: %s)' %
                             flask_app.config.server.port)
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Increase verbosity')

    opts = parser.parse_args()

    return opts


def create_context():
    if hasattr(ssl, 'create_default_context'):  # Python >= 2.7.9
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    else:
        context = LegacySSLContext()

    context.load_cert_chain(
        certfile=flask_app.config.server.ssl.cert_chain,
        keyfile=flask_app.config.server.ssl.key)
    context.set_ciphers(flask_app.config.server.ssl.ciphers)
    return context


class LegacySSLContext(object):
    """Wrap ssl.wrap_socket in a class with the SSLContext API"""

    _ciphers = None

    def load_cert_chain(self, certfile, keyfile):
        self._certfile = certfile
        self._keyfile = keyfile

    def set_ciphers(self, ciphers):
        self._ciphers = ciphers

    def wrap_socket(self, sock, **kwargs):
        return ssl.wrap_socket(
            sock, certfile=self._certfile, keyfile=self._keyfile,
            ciphers=self._ciphers, **kwargs)


if __name__ == '__main__':
    flask_app = create_app(find_deploy_config())
    opts = parse_args(flask_app)
    configure_logging(opts.debug, flask_app.config.server.logging)
    context = create_context()
    log.debug('Starting yodeploy server')
    flask_app.run(host=opts.listen, port=opts.port, ssl_context=context)
