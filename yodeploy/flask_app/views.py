import logging
import os

from flask import Blueprint, abort, current_app, jsonify, request

from yodeploy.application import Application
from yodeploy.deploy import available_applications, deploy
from yodeploy.flask_app.auth import auth

log = logging.getLogger('yodeploy')

yodeploy_blueprint = Blueprint('yodeploy_server', __name__)


@yodeploy_blueprint.route('/deploy/<app>', methods=['GET', 'POST'])
@auth.login_required
def deploy_app(app):
    if app not in available_applications(current_app.config):
        abort(404)
    if request.method == 'POST':
        log.debug('Request to deploy %s', app)
        if request.form:
            log.debug('Extra arguments: %s', request.form)
        target = request.form.get('target', 'master')
        version = request.form.get('version')
        user = request.form.get('user')
        deploy(app, target, current_app.config.deploy_config_fn, version,
               current_app.config, user)
        log.info('Version %s of %s successfully deployed', version, app)
    application = Application(app, current_app.config.deploy_config_fn)
    version = application.live_version
    return jsonify({'application': {'name': app, 'version': version}})


@yodeploy_blueprint.route('/deploy/', methods=['GET'])
@auth.login_required
def get_all_deployed_versions():
    result = []
    apps = available_applications(current_app.config)
    for app in apps:
        appdir = os.path.join(current_app.config.paths.apps, app)
        app_result = {
            'name': app,
            'version': None
        }
        if os.path.isdir(appdir):
            application = Application(app, current_app.config.deploy_config_fn)
            app_result['version'] = application.live_version
        result.append(app_result)
    return jsonify({'applications': result})
