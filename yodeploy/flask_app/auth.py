from flask_httpauth import HTTPBasicAuth


auth = HTTPBasicAuth()


@auth.verify_password
def get_pw(username, password):
    """Check if a username / password combination is valid."""
    from flask import current_app
    return (username == current_app.config.server.username and
            password == current_app.config.server.password)
