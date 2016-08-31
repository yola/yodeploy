import unittest

from mock import PropertyMock, call, patch

from yodeploy.hooks.django import DjangoApp, parse_django_version


class TestDjangoHook(unittest.TestCase):

    def setUp(self):
        self.dh = DjangoApp('test', None, '/tmp/test', '123', {}, None)

    def test_vhost_attributes(self):
        self.assertEqual(self.dh.vhost_path, '/etc/apache2/sites-enabled')


class TestParseDjangoVersion(unittest.TestCase):
    def test_parses_major_and_minor_from_alpha_version_number(self):
        self.assertEqual(parse_django_version('1.9a1'), (1, 9))

    def test_parses_double_digit_minor_version(self):
        self.assertEqual(parse_django_version('1.10'), (1, 10))

    def test_parses_single_digit_minor_version(self):
        self.assertEqual(parse_django_version('1.5'), (1, 5))


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
        self.mock_django_version.return_value = (1, 5)
        self.dh.run_migrate_commands()
        self.mock_manage_py.assert_called_once_with('syncdb', '--noinput')

    def test_call_syncdb_then_migrate_for_django_1_5_with_migrations(self):
        """Call syncdb then migrate for Django 1.5 with migrations"""
        self.mock_django_version.return_value = (1, 5)
        self.dh.has_migrations = True
        self.dh.run_migrate_commands()
        self.mock_manage_py.assert_has_calls(
            [call('syncdb', '--noinput'), call('migrate')])

    def test_call_migrate_for_django_1_7(self):
        """Call migrate for Django 1.7"""
        self.mock_django_version.return_value = (1, 7)
        self.dh.run_migrate_commands()
        self.mock_manage_py.assert_called_once_with('migrate', '--noinput')

    def test_call_migrate_for_django_1_10(self):
        """Call migrate for Django 1.10"""
        self.mock_django_version.return_value = (1, 10)
        self.dh.run_migrate_commands()
        self.mock_manage_py.assert_called_once_with('migrate', '--noinput')
