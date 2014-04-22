from functools import wraps

from flask import request, Response


def check_auth(config, username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'fieldhq' and password == config.server.password


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response('Could not verify your access level for that URL.\n'
                    'You have to login with proper credentials', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def auth_decorator(config):
    def requires_auth(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not check_auth(config, auth.username, auth.password):
                return authenticate()
            return f(*args, **kwargs)
        return decorated
    return requires_auth
