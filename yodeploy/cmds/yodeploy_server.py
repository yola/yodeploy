import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from OpenSSL import SSL

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


if __name__ == '__main__':
    flask_app = create_app(find_deploy_config())
    opts = parse_args(flask_app)
    configure_logging(opts.debug, flask_app.config.server.logging)
    context = SSL.Context(SSL.SSLv23_METHOD)
    context.use_certificate_chain_file(flask_app.config.server.ssl.cert_chain)
    context.use_privatekey_file(flask_app.config.server.ssl.key)
    flask_app.config['SERVER_NAME'] = '%s:%s' % (opts.listen, opts.port)
    flask_app.config.deploy_config_fn = find_deploy_config()
    log.debug('Starting yodeploy server')
    flask_app.run(host=opts.listen, port=opts.port, ssl_context=context)
