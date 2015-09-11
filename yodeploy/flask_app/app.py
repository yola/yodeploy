import logging

from flask import Flask
from yoconfigurator.dicts import DotDict

from yodeploy.config import load_settings
from yodeploy.flask_app.auth import auth
from yodeploy.flask_app.errors import not_found, server_error

log = logging.getLogger('yodeploy')


def create_app(settings_fn):
    app = Flask(__name__)
    app.config = DotDict(app.config)
    app.config.update(load_settings(settings_fn))
    app.config.deploy_config_fn = settings_fn

    from yodeploy.flask_app.views import yodeploy_blueprint
    app.register_blueprint(yodeploy_blueprint)

    @app.errorhandler(404)
    @auth.login_required
    def not_found_error(error):
        return not_found()

    @app.errorhandler(500)
    def internal_server_error(error):
        return server_error()

    return app
