from unittest import TestCase

from mock import call, patch

from yodeploy.hooks.nginx import NginxHostedApp


class TestNginxHostedAppPrepareHook(TestCase):
    def setUp(self):
        self.dh = NginxHostedApp(
            'nginx-app', None, '/tmp/test', '123', {}, None
        )

        touch_patcher = patch('yodeploy.hooks.nginx.touch')
        self.touch_mock = touch_patcher.start()
        self.addCleanup(touch_patcher.stop)

        template_patcher = patch.object(self.dh, 'template')
        self.template_mock = template_patcher.start()
        self.addCleanup(template_patcher.stop)

        configurator_prepare_patcher = patch.object(
            self.dh, 'configurator_prepare'
        )
        configurator_prepare_patcher.start()
        self.addCleanup(configurator_prepare_patcher.stop)

    def test_places_logfiles(self):
        self.dh.prepare()

        self.touch_mock.assert_has_calls(
            [
                call('/var/log/nginx/nginx-app-access.log',
                     'www-data', 'adm', 0o640),
                call('/var/log/nginx/nginx-app-error.log',
                     'www-data', 'adm', 0o640),
            ],
            any_order=True
        )

    def test_places_server_block(self):
        self.dh.prepare()

        self.template_mock.assert_called_once_with(
            'nginx/server_block.conf.template',
            '/etc/nginx/sites-enabled/nginx-app'
        )


class TestNginxHostedAppDeployedHook(TestCase):
    def setUp(self):
        self.dh = NginxHostedApp('test', None, '/tmp/test', '123', {}, None)

    @patch('yodeploy.hooks.nginx.NginxHostedApp.configurator_deployed')
    @patch('yodeploy.hooks.nginx.subprocess.check_call')
    def test_restarts_nginx(self, check_call_mock, *args):
        self.dh.deployed()

        check_call_mock.assert_called_once_with(('service', 'nginx', 'reload'))
