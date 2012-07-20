import os

from yola.configurator.dicts import DotDict

from ..application import Application
from ..artifacts import LocalArtifacts

from . import TmpDirTestCase


class ApplicationTest(TmpDirTestCase):
    def artifact_factory(self, filename=None, app=None):
        return LocalArtifacts('test', None, self.tmppath('state'),
                              self.tmppath('artifacts'))

    def setUp(self):
        super(ApplicationTest, self).setUp()
        settings = DotDict(
                paths={
                    'root': self.tmppath('srv'),
                },
        )
        self.app = Application('test', None, self.artifact_factory, settings)

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

    def test_locking(self):
        self.app.lock()
        self.assertRaises(Exception, self.app.lock)
        self.app.unlock()

    def test_unpack(self):
        self.create_tar('test.tar.gz', 'foo/bar')
        self.app.artifacts.upload(self.tmppath('test.tar.gz'))
        version = self.app.artifacts.versions.latest.version_id
        os.unlink(self.tmppath('test.tar.gz'))

        self.app.lock()
        self.app.unpack(version)
        self.app.unlock()

        self.assertTMPPExists('srv', 'test', 'versions', version)
        self.assertTMPPExists('srv', 'test', 'versions', version, 'bar')

    def test_double_unpack(self):
        self.create_tar('test.tar.gz', 'foo/bar')
        self.app.artifacts.upload(self.tmppath('test.tar.gz'))
        version = self.app.artifacts.versions.latest.version_id
        os.unlink(self.tmppath('test.tar.gz'))

        self.app.lock()
        self.app.unpack(version)
        self.app.unpack(version)
        self.app.unlock()

        self.assertTMPPExists('srv', 'test', 'versions', version)
        self.assertTMPPExists('srv', 'test', 'versions', version, 'bar')

    def test_unpack_live(self):
        self.create_tar('test.tar.gz', 'foo/bar')
        self.app.artifacts.upload(self.tmppath('test.tar.gz'))
        version = self.app.artifacts.versions.latest.version_id
        os.unlink(self.tmppath('test.tar.gz'))

        os.makedirs(self.tmppath('srv', 'test', 'versions', version))
        os.symlink(os.path.join('versions', version),
                   self.tmppath('srv', 'test', 'live'))
        self.assertEqual(self.app.live_version, version)

        self.app.lock()
        self.assertRaises(Exception, self.app.unpack, version)
        self.app.unlock()

    def test_swing_symlink_create(self):
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'foobar'))

        self.app.lock()
        self.app.swing_symlink('foobar')
        self.app.unlock()

        self.assertTMPPExists('srv', 'test', 'live')
        self.assertEqual(self.app.live_version, 'foobar')

    def test_swing_symlink_overwrite(self):
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'foo'))
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'bar'))
        os.symlink(os.path.join('versions', 'foo'),
                   self.tmppath('srv', 'test', 'live'))

        self.assertEqual(self.app.live_version, 'foo')

        self.app.lock()
        self.app.swing_symlink('bar')
        self.app.unlock()

        self.assertTMPPExists('srv', 'test', 'live')
        self.assertEqual(self.app.live_version, 'bar')
