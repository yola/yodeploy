import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


from flask import abort, Flask, jsonify, make_response, request
from OpenSSL import SSL

from yodeploy.application import Application
from yodeploy.config import find_deploy_config, load_settings
from yodeploy.flask_auth import auth_decorator
from yodeploy.deploy import available_applications, deploy, configure_logging
from yodeploy.repository import get_repository

flask_app = Flask(__name__)

deploy_settings_fn = find_deploy_config()
deploy_settings = load_settings(deploy_settings_fn)
repository = get_repository(deploy_settings)


@flask_app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Server error'}), 500


@flask_app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@flask_app.route('/deploy/<app>/', methods=['GET', 'POST'])
@auth_decorator(deploy_settings)
def deploy_app(app):
    if app not in available_applications(deploy_settings):
        abort(404)
    if request.method == 'POST':
        log.debug('Request to deploy %s', app)
        if request.form:
            log.debug('Extra arguments: %s', request.form)
        target = request.form.get('target', 'master')
        version = request.form.get('version')
        deploy(app, target, deploy_settings_fn, version, deploy_settings)
        log.info('Version %s of %s successfully deployed', version, app)
    application = Application(app, deploy_settings_fn)
    version = application.live_version
    return jsonify({'application': {'name': app, 'version': version}})


@flask_app.route('/deploy/', methods=['GET'])
@auth_decorator(deploy_settings)
def get_all_deployed_versions():
    result = []
    apps = available_applications(deploy_settings)
    for app in apps:
        appdir = os.path.join(deploy_settings.paths.apps, app)
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
                        default=deploy_settings.server.port,
                        help='Port to listen on (default: %s)' %
                             deploy_settings.server.port)
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Increase verbosity')

    opts = parser.parse_args()

    return opts


if __name__ == '__main__':
    opts = parse_args()
    configure_logging(opts.debug, deploy_settings.logging)
    log = logging.getLogger('yodeploy')
    context = SSL.Context(SSL.SSLv23_METHOD)
    context.use_certificate_chain_file(deploy_settings.server.ssl.cert_chain)
    context.use_privatekey_file(deploy_settings.server.ssl.key)
    log.debug('Starting yodeploy server')
    flask_app.run(host=opts.host, port=opts.port,
                  ssl_context=context)
