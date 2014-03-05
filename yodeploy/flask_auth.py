import os
from functools import wraps

from flask import request, Response
from yoconfigurator.base import read_config
from yoconfigurator.credentials import seeded_auth_token

from yodeploy.config import find_deploy_config, load_settings


# Set defaults
config = find_deploy_config(False)
deploy_settings = load_settings(config)

QA = True if deploy_settings.build.environment == 'qa' else False
config = read_config(os.path.join('.')) if QA else read_config(os.path.join('', 'srv', 'yodeploy', 'live'))


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return password == seeded_auth_token(username, 'yodeploy', config.common.api_seed)


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response('Could not verify your access level for that URL.\n'
                    'You have to login with proper credentials', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated
