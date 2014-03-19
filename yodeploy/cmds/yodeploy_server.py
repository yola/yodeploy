import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from flask import abort, Flask, jsonify, make_response, request
from OpenSSL import SSL
from yoconfigurator.base import read_config

from yodeploy.application import Application
from yodeploy.config import find_deploy_config, load_settings
from yodeploy.flask_auth import auth_decorator
from yodeploy.deploy import available_applications, deploy
from yodeploy.repository import get_repository

flask_app = Flask(__name__)

# Set defaults
deploy_settings_fn = find_deploy_config(False)
deploy_settings = load_settings(deploy_settings_fn)
repository = get_repository(deploy_settings)


@flask_app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


@flask_app.route('/deploy/<app>/', methods=['GET', 'POST'])
@auth_decorator(deploy_settings)
def deploy_app(app):
    if app not in available_applications(deploy_settings):
        abort(404)
    if request.method == 'POST':
        target = request.form.get('target', 'master')
        version = request.form.get('version')
        deploy(app, target, deploy_settings_fn, version, deploy_settings)
    application = Application(app, deploy_settings_fn)
    version = application.live_version
    return jsonify({'application': {'name': app, 'version': version}})


@flask_app.route('/deploy/', methods=['GET'])
@auth_decorator(deploy_settings)
def get_all_deployed_versions():
    result = []
    apps = available_applications(deploy_settings)
    for app in apps:
        application = Application(app, deploy_settings_fn)
        version = application.live_version
        result.append({
            'name': app,
            'version': version
        })
    return jsonify({'applications': result})


if __name__ == '__main__':
    context = SSL.Context(SSL.TLSv1_METHOD)
    context.use_certificate_chain_file(deploy_settings.server.ssl.cert_chain)
    context.use_privatekey_file(deploy_settings.server.ssl.key)
    flask_app.run(host='0.0.0.0', port=deploy_settings.server.port,
                  ssl_context=context)
