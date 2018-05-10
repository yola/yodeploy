import unittest

from mock import PropertyMock, call, patch
from pkg_resources import parse_version

from yodeploy.hooks.django import ApacheHostedDjangoApp, DjangoApp


class TestApacheHostedDjangoHook(unittest.TestCase):

    def setUp(self):
        self.dh = ApacheHostedDjangoApp(
            'test', None, '/tmp/test', '123', {}, None)

    def test_vhost_attributes(self):
        self.assertEqual(self.dh.vhost_path, '/etc/apache2/sites-enabled')


class TestDjangoMigrateCommand(unittest.TestCase):
    def setUp(self):
        django_version_patcher = patch.object(
            DjangoApp, 'django_version', new_callable=PropertyMock)
        self.mock_django_version = django_version_patcher.start()
        self.addCleanup(django_version_patcher.stop)

        manage_py_patcher = patch.object(DjangoApp, 'manage_py')
        self.mock_manage_py = manage_py_patcher.start()
        self.addCleanup(manage_py_patcher.stop)

        self.dh = DjangoApp('test', None, '/tmp/test', '123', {}, None)

    def test_call_syncdb_for_django_1_5(self):
        """Call syncdb for django 1.5"""
        self.mock_django_version.return_value = parse_version('1.5')
        self.dh.run_migrate_commands()
        self.mock_manage_py.assert_called_once_with('syncdb', '--noinput')

    def test_call_syncdb_then_migrate_for_django_1_5_with_migrations(self):
        """Call syncdb then migrate for Django 1.5 with migrations"""
        self.mock_django_version.return_value = parse_version('1.5')
        self.dh.has_migrations = True
        self.dh.run_migrate_commands()
        self.mock_manage_py.assert_has_calls(
            [call('syncdb', '--noinput'), call('migrate')])

    def test_call_migrate_for_django_1_7(self):
        """Call migrate for Django 1.7"""
        self.mock_django_version.return_value = parse_version('1.7')
        self.dh.run_migrate_commands()
        self.mock_manage_py.assert_called_once_with('migrate', '--noinput')

    def test_call_migrate_for_django_1_10(self):
        """Call migrate for Django 1.10"""
        self.mock_django_version.return_value = parse_version('1.10')
        self.dh.run_migrate_commands()
        self.mock_manage_py.assert_called_once_with('migrate', '--noinput')
