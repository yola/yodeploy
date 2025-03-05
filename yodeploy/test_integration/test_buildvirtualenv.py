import os
import unittest

from yodeploy.test_integration.helpers import build_sample, cleanup_venv


def venv_path(app):
    samples = os.path.join(os.path.dirname(__file__), 'samples')
    return os.path.join(samples, app, 'virtualenv.tar.gz')


class TestAppWithEmptyRequirements(unittest.TestCase):
    def setUp(self):
        cleanup_venv('requirements-empty')
        build_sample('requirements-empty')

    def test_has_a_virtualenv(self):
        venv_path = os.path.join(
            os.path.dirname(__file__),
            'samples/requirements-empty/virtualenv.tar.gz')
        has_venv = os.path.exists(venv_path)
        self.assertTrue(has_venv)


class TestAppWithRequirementsThatDowngrade(unittest.TestCase):

    def setUp(self):
        cleanup_venv('requirements-downgrade')

    def test_fails_to_build(self):
        with self.assertRaises(Exception):
            build_sample('requirements-downgrade')
