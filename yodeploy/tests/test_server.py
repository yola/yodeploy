import base64
import json

from yoconfigurator.tests import unittest

from yodeploy.cmds import yodeploy_server
from yodeploy.config import find_deploy_config, load_settings
from yodeploy.tests.samples.helpers import deployconf_fn


deploy_settings = load_settings(find_deploy_config())


class ServerTestCase(unittest.TestCase):
    def setUp(self):
        self.username = deploy_settings.server.username
        self.password = deploy_settings.server.password

        self.auth_header = {
            'Authorization': 'Basic ' + base64.b64encode(
                '%s:%s' % (self.username, self.password))
        }

        yodeploy_server.flask_app.config.update(load_settings(deployconf_fn))
        yodeploy_server.deploy_settings_fn = deployconf_fn

        self.app = yodeploy_server.flask_app.test_client()

    def test_no_auth_fails(self):
        response = self.app.get('/deploy/')
        self.assertEqual(response.headers['WWW-Authenticate'],
                         'Basic realm="Login Required"')
        self.assertEqual(response.status_code, 401)

    def test_with_auth(self):
        response = self.app.get('/deploy/', headers=self.auth_header)
        self.assertEqual(response.status_code, 200)

    def test_get_deployed_apps(self):
        response = self.app.get('/deploy/', headers=self.auth_header)
        json_response = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue('applications' in json_response)
        self.assertTrue(
            'basic-app' in app['name'] for app in json_response['applications']
        )

    def test_get_deployed_basic_app_version(self):
        response = self.app.get('/deploy/basic-app/', headers=self.auth_header)
        json_response = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue('application' in json_response)
        self.assertEqual(json_response['application']['name'], 'basic-app')
        self.assertEqual(json_response['application']['version'], '1')

    def test_deploy_basic_app_latest_version(self):
        response = self.app.post(
            '/deploy/basic-app/', headers=self.auth_header)
        json_response = json.loads(response.data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue('application' in json_response)
        self.assertEqual(json_response['application']['name'], 'basic-app')
        self.assertEqual(json_response['application']['version'], '1')
