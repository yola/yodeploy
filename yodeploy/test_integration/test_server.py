import base64
import json
import unittest

from yodeploy.flask_app.app import create_app
from yodeploy.test_integration.helpers import (
    build_sample, clear, deploy_sample, deployconf_fn)


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        clear('basic-app')
        build_sample('basic-app')
        deploy_sample('basic-app')

        self.flask_app = create_app(deployconf_fn)

        self.username = self.flask_app.config.server.username
        self.password = self.flask_app.config.server.password

        auth_header_val = '%s:%s' % (self.username, self.password)
        auth_header_val = auth_header_val.encode()
        auth_header_val = b'Basic %s' % base64.b64encode(auth_header_val)

        self.auth_header = {
            'Authorization': auth_header_val
        }

        self.app = self.flask_app.test_client()

    def assertResponse(self, response, status_code=200, headers=None):
        self.assertEqual(response.status_code, status_code)

        headers = headers or {}
        for header, value in headers.items():
            self.assertEqual(response.headers[header], value)

    def assertDeployedApps(self, response, status_code=200, headers=None,
                           apps=None):
        self.assertResponse(response, status_code, headers)

        json_response = json.loads(response.data.decode())

        self.assertTrue('applications' in json_response)

        apps = apps or []
        for app in apps:
            deployed_app_names = [
                deployed_app['name'] for deployed_app in
                json_response['applications']]
            self.assertTrue(
                any(app == app_name for app_name in deployed_app_names))

    def assertDeployedApp(self, response, status_code=200, headers=None,
                          name=None, version='1'):
        self.assertResponse(response, status_code, headers)

        json_response = json.loads(response.data.decode())

        self.assertTrue('application' in json_response)

    def test_no_auth_fails(self):
        response = self.app.get('/deploy/')
        self.assertResponse(
            response, status_code=401,
            headers={
                'WWW-Authenticate': 'Basic realm="Authentication Required"'})

    def test_with_auth(self):
        response = self.app.get('/deploy/', headers=self.auth_header)
        self.assertResponse(response)

    def test_get_deployed_apps(self):
        response = self.app.get('/deploy/', headers=self.auth_header)
        self.assertDeployedApps(response, apps=['basic-app'])

    def test_get_deployed_basic_app_version(self):
        response = self.app.get('/deploy/basic-app', headers=self.auth_header)

        self.assertDeployedApp(response, name='basic-app')

    def test_deploy_basic_app_latest_version(self):
        response = self.app.post(
            '/deploy/basic-app', headers=self.auth_header)

        self.assertDeployedApp(response, name='basic-app')
