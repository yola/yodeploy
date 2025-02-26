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

    def test_force_rebuild_creates_virtualenv(self):
        build_sample('requirements-empty')
        initial_mtime = os.path.getmtime(venv_path('requirements-empty'))
        build_sample('requirements-empty', force_rebuild=True)
        new_mtime = os.path.getmtime(venv_path('requirements-empty'))
        self.assertTrue(os.path.exists(venv_path('requirements-empty')))
        self.assertGreater(new_mtime, initial_mtime, "VE was not rebuilt with --force-rebuild")


class TestAppWithRequirementsThatDowngrade(unittest.TestCase):

    def setUp(self):
        cleanup_venv('requirements-downgrade')

    def test_fails_to_build(self):
        with self.assertRaises(Exception):
            build_sample('requirements-downgrade')

    def test_fails_to_build_with_force_rebuild(self):
        with self.assertRaises(Exception):
            build_sample('requirements-downgrade', force_rebuild=True)
