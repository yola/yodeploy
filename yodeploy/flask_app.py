import os
import subprocess

from flask import abort, Flask, jsonify, make_response, request

flask_app = Flask(__name__)


def get_available_apps():
    proc = subprocess.Popen('deploy a', shell=True, stdout=subprocess.PIPE)
    shell_output = proc.stdout.read()
    apps = []
    if shell_output != 'No available applications\n':
        apps = apps.replace(' * ', '').split('\n')[1:-1]
    return apps


def get_app_version(app):
    livepath = '/srv/%s/live/' % app
    realpath = os.path.realpath(livepath)
    version = realpath[realpath.rfind('/') + 1:]
    return version


@flask_app.errorhandler(404)
def not_found(error):
    return make_response(jsonify( { 'error': 'Not found' } ), 404)


@flask_app.route('/deploy/<app>/', methods=['GET', 'POST'])
def deploy_app(app):
    version = get_app_version(app)
    if version == '' or app not in get_available_apps():
        abort(404)
    if request.method == 'POST':
        proc = subprocess.Popen('deploy deploy %s' % app, shell=True)
        proc.wait()
        version = get_app_version(app)
    return jsonify({'application': {'name': app, 'version': version}})


@flask_app.route('/deploy/', methods=['GET'])
def get_all_deploy_versions():
    result = []
    apps = get_available_apps()
    for app in apps:
        version = get_app_version(app)
        result.append({
            'name': app,
            'version': version
        })
    return jsonify({'applications': result})


if __name__ == '__main__':
    flask_app.run(port=10000)
