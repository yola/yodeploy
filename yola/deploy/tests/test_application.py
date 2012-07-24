import os

from ..application import Application
from ..artifacts import LocalArtifacts

from . import TmpDirTestCase


class ApplicationTest(TmpDirTestCase):
    def artifact_factory(self, filename=None, app=None):
        return LocalArtifacts('test', None, self.tmppath('state'),
                              self.tmppath('artifacts'))

    def setUp(self):
        super(ApplicationTest, self).setUp()
        with open(self.tmppath('config.py'), 'w') as f:
            f.write("""
class AttrDict(dict):
    __getattr__ = dict.__getitem__

deploy_settings = AttrDict(paths=AttrDict(root='%s'))
""" % self.tmppath('srv'))
        self.app = Application('test', None, self.artifact_factory,
                               self.tmppath('config.py'))

    def test_attributes(self):
        self.assertEqual(self.app.app, 'test')
        self.assertTrue(self.app.target is None)
        self.assertTrue(isinstance(self.app.artifacts, LocalArtifacts))
        self.assertTrue(isinstance(self.app.settings, dict))
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

    def test_swing_symlink_stale_live_new(self):
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'foo'))
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'bar'))
        os.symlink(os.path.join('versions', 'foo'),
                   self.tmppath('srv', 'test', 'live.new'))

        self.app.lock()
        self.app.swing_symlink('bar')
        self.app.unlock()

        self.assertTMPPExists('srv', 'test', 'live')
        self.assertNotTMPPExists('srv', 'test', 'live.new')
        self.assertEqual(self.app.live_version, 'bar')

    def test_prepare_hook(self):
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'foo', 'deploy'))
        with open(self.tmppath('srv', 'test', 'versions', 'foo', 'deploy',
                               'hooks.py'), 'w') as f:
            f.write("""import os

from yola.deploy.hooks.base import DeployHook


class Hooks(DeployHook):
    def prepare(self):
        open(os.path.join(self.root, 'hello'), 'w').close()


hooks = Hooks
""")
        self.app.lock()
        self.app.prepare('foo')
        self.app.unlock()
        self.assertTMPPExists('srv', 'test', 'hello')

    def test_deployed(self):
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'foo', 'deploy'))
        with open(self.tmppath('srv', 'test', 'versions', 'foo', 'deploy',
                               'hooks.py'), 'w') as f:
            f.write("""import os

from yola.deploy.hooks.base import DeployHook


class Hooks(DeployHook):
    def deployed(self):
        open(os.path.join(self.root, 'hello'), 'w').close()


hooks = Hooks
""")
        self.app.lock()
        self.app.deployed('foo')
        self.app.unlock()
        self.assertTMPPExists('srv', 'test', 'hello')

    def test_deploy(self):
        self.create_tar('test.tar.gz', 'foo/bar', contents={
            'foo/deploy/hooks.py': """import os

from yola.deploy.hooks.base import DeployHook


class Hooks(DeployHook):
    def prepare(self):
        open(os.path.join(self.root, 'hello'), 'w').close()
    def deployed(self):
        open(os.path.join(self.root, 'there'), 'w').close()


hooks = Hooks
"""})
        self.app.artifacts.upload(self.tmppath('test.tar.gz'))
        version = self.app.artifacts.versions.latest.version_id
        os.unlink(self.tmppath('test.tar.gz'))

        self.app.deploy(version)
        self.assertTMPPExists('srv', 'test', 'versions', version, 'bar')
        self.assertTMPPExists('srv', 'test', 'live', 'bar')
        self.assertTMPPExists('srv', 'test', 'hello')
        self.assertTMPPExists('srv', 'test', 'there')
