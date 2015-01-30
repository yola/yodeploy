import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from flask import Flask, abort, jsonify, request
from OpenSSL import SSL
from yoconfigurator.dicts import DotDict

from yodeploy.application import Application
from yodeploy.config import find_deploy_config, load_settings
from yodeploy.flask_auth import auth_decorator
from yodeploy.deploy import available_applications, configure_logging, deploy
from yodeploy.repository import get_repository

log = logging.getLogger('yodeploy')

flask_app = Flask(__name__)

deploy_settings_fn = find_deploy_config()

flask_app.config.update(load_settings(deploy_settings_fn))

repository = get_repository(DotDict(flask_app.config))


@flask_app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Server error'}), 500


@flask_app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@flask_app.route('/deploy/<app>/', methods=['GET', 'POST'])
@auth_decorator(DotDict(flask_app.config))
def deploy_app(app):
    if app not in available_applications(DotDict(flask_app.config)):
        abort(404)
    if request.method == 'POST':
        log.debug('Request to deploy %s', app)
        if request.form:
            log.debug('Extra arguments: %s', request.form)
        target = request.form.get('target', 'master')
        version = request.form.get('version')
        deploy(app, target, deploy_settings_fn, version,
               DotDict(flask_app.config))
        log.info('Version %s of %s successfully deployed', version, app)
    application = Application(app, deploy_settings_fn)
    version = application.live_version
    return jsonify({'application': {'name': app, 'version': version}})


@flask_app.route('/deploy/', methods=['GET'])
@auth_decorator(DotDict(flask_app.config))
def get_all_deployed_versions():
    result = []
    apps = available_applications(DotDict(flask_app.config))
    for app in apps:
        appdir = os.path.join(DotDict(flask_app.config).paths.apps, app)
        app_result = {
            'name': app,
            'version': None
        }
        if os.path.isdir(appdir):
            application = Application(app, deploy_settings_fn)
            app_result['version'] = application.live_version
        result.append(app_result)
    return jsonify({'applications': result})


def parse_args():
    parser = argparse.ArgumentParser(description="Yodeploy server")

    parser.add_argument('--listen', '-l', help='Bind to this IP address',
                        default='0.0.0.0')
    parser.add_argument('--port', '-p', type=int,
                        default=DotDict(flask_app.config).server.port,
                        help='Port to listen on (default: %s)' %
                             DotDict(flask_app.config).server.port)
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Increase verbosity')

    opts = parser.parse_args()

    return opts


if __name__ == '__main__':
    opts = parse_args()
    configure_logging(opts.debug, DotDict(flask_app.config).server.logging)
    context = SSL.Context(SSL.SSLv23_METHOD)
    context.use_certificate_chain_file(
        DotDict(flask_app.config).server.ssl.cert_chain)
    context.use_privatekey_file(DotDict(flask_app.config).server.ssl.key)
    log.debug('Starting yodeploy server')
    flask_app.run(host=opts.listen, port=opts.port, ssl_context=context)
