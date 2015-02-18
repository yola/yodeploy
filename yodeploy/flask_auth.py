from functools import wraps

from flask import jsonify, request


def check_auth(username, password):
    """Check if a username / password combination is valid."""
    from flask import current_app
    return (username == current_app.config.server.username
            and password == current_app.config.server.password)


def authenticate():
    """Send a 401 response that enables basic auth."""
    return (
        jsonify({'error': 'Could not verify your access level for that URL.\n'
                          'You have to login with proper credentials'}),
        401,
        {'WWW-Authenticate': 'Basic realm="yodeploy"'})


def auth_decorator():
    def requires_auth(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password):
                return authenticate()
            return f(*args, **kwargs)
        return decorated
    return requires_auth
