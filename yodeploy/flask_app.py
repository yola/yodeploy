import os

from flask import abort, Flask, jsonify, make_response, request
from yoconfigurator.base import read_config

from yodeploy.application import Application
from yodeploy.config import find_deploy_config, load_settings
from yodepoy.flask_auth import requires_auth
from yodeploy.deploy import available_applications, deploy
from yodeploy.repository import get_repository

flask_app = Flask(__name__)

# Set defaults
config = find_deploy_config(False)
deploy_settings = load_settings(config)
repository = get_repository(deploy_settings)

QA = True if deploy_settings.build.environment == 'qa' else False
config = read_config(os.path.join('.')) if QA else read_config(os.path.join('', 'srv', 'yodeploy', 'live'))


@flask_app.errorhandler(404)
def not_found(error):
    return make_response(jsonify({'error': 'Not found'}), 404)


@flask_app.route('/deploy/<app>/', methods=['GET', 'POST'])
@requires_auth
def deploy_app(app, version=None, target='master'):
    if app not in available_applications(deploy_settings):
        abort(404)
    if request.method == 'POST':
        target = request.form.get('target')
        version = request.form.get('version')
        deploy(app, target, config, version, deploy_settings)
    application = Application(app, target, repository, config)
    version = application.live_version
    return jsonify({'application': {'name': app, 'version': version}})


@flask_app.route('/deploy/', methods=['GET'])
@requires_auth
def get_all_deploy_versions():
    result = []
    apps = available_applications(deploy_settings)
    for app in apps:
        application = Application(app=app, target='master', repository=repository, settings_file=config)
        version = application.live_version
        result.append({
            'name': app,
            'version': version
        })
    return jsonify({'applications': result})


if __name__ == '__main__':
    flask_app.run(port=10000)
