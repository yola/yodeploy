from unittest import TestCase

from mock import patch

from yodeploy.hooks.uwsgi import UwsgiHostedApp


class TestUwsgiHostedAppPrepareHook(TestCase):
    def setUp(self):
        self.dh = UwsgiHostedApp(
            'uwsgi-app', None, '/tmp/test', '123', {}, None
        )

        touch_patcher = patch('yodeploy.hooks.uwsgi.touch')
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

    def test_places_logfile(self):
        self.dh.prepare()

        self.touch_mock.assert_called_once_with(
            '/var/log/uwsgi/uwsgi-app.log', 'www-data', 'adm', 0o640
        )

    def test_places_config_ini(self):
        self.dh.prepare()

        self.template_mock.assert_called_once_with(
            'uwsgi/config.ini.template',
            '/etc/uwsgi/uwsgi-app.ini'
        )


class TestUwsgiHostedAppDeployedHook(TestCase):
    def setUp(self):
        self.dh = UwsgiHostedApp('test', None, '/tmp/test', '123', {}, None)

    @patch('yodeploy.hooks.uwsgi.UwsgiHostedApp.configurator_deployed')
    @patch('yodeploy.hooks.uwsgi.subprocess.check_call')
    def test_restarts_uwsgi(self, check_call_mock, *args):
        self.dh.deployed()

        check_call_mock.assert_called_once_with(('service', 'uwsgi', 'reload'))
