import os
import shutil
import tempfile
import unittest

from yola.configurator.dicts import DotDict

from ..application import Application
from ..artifacts import LocalArtifacts


class ApplicationTest(unittest.TestCase):
    def artifact_factory(self, filename=None, app=None):
        return LocalArtifacts('test', None, self.tmppath('state'),
                              self.tmppath('artifacts'))

    def tmppath(self, *fragments):
        return os.path.join(self.tmpdir, *fragments)

    def mkdir(self, *fragments):
        os.makedirs(self.tmppath(*fragments))

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='yola.deploy-test')
        settings = DotDict(
                paths={
                    'root': self.tmppath('srv'),
                },
        )
        self.app = Application('test', None, self.artifact_factory, settings)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_attributes(self):
        self.assertEqual(self.app.app, 'test')
        self.assertTrue(self.app.target is None)
        self.assertTrue(isinstance(self.app.artifacts, LocalArtifacts))
        self.assertTrue(isinstance(self.app.settings, DotDict))
        self.assertEqual(self.app.appdir, self.tmppath('srv', 'test'))

    def test_live_version_never_deployed(self):
        self.assertTrue(self.app.live_version is None)

    def test_live_version(self):
        self.mkdir('srv', 'test', 'versions', 'foobar')
        os.symlink(os.path.join('versions', 'foobar'),
                   self.tmppath('srv', 'test', 'live'))
        self.assertEqual(self.app.live_version, 'foobar')
