import os
import shutil

from ..application import Application
from ..repository import LocalRepositoryStore, Repository
from ..virtualenv import ve_version, sha224sum, create_ve, upload_ve

from . import TmpDirTestCase


class ApplicationTest(TmpDirTestCase):

    def setUp(self):
        super(ApplicationTest, self).setUp()
        with open(self.tmppath('config.py'), 'w') as f:
            f.write("""
class AttrDict(dict):
    __getattr__ = dict.__getitem__

deploy_settings = AttrDict(
    artifacts=AttrDict(
        store='local',
        store_settings=AttrDict(
            local=AttrDict(
                directory='%s',
            ),
        ),
    ),
    paths=AttrDict(
        apps='%s',
    ),
)
""" % (self.tmppath('artifacts'), self.tmppath('srv')))

        store = LocalRepositoryStore(self.mkdir('artifacts'))
        self.repo = Repository(store)
        self.app = Application('test', 'master', self.repo,
                               self.tmppath('config.py'))
        if not os.path.exists('test-data/deploy-ve/virtualenv.tar.gz'):
            self._create_test_ve()
        self._deploy_ve_hash = ve_version(sha224sum(
            'test-data/deploy-ve/requirements.txt'))

    def _create_test_ve(self):
        """
        Bootstrap a deploy virtualenv, for our tests
        This needs a PYPI that contains yodeploy
        """
        pypi = os.environ.get('PYPI')
        if not pypi:
            import yodeploy.config
            deploy_settings = yodeploy.config.load_settings(
                    yodeploy.config.find_deploy_config())
            pypi = deploy_settings.build.pypi

        if os.path.exists('test-data/deploy-ve'):
            shutil.rmtree('test-data/deploy-ve')
        os.makedirs('test-data/deploy-ve')
        if not os.path.exists('test-data/deploy-ve/requirements.txt'):
            with open('test-data/deploy-ve/requirements.txt', 'w') as f:
                f.write('yodeploy\n')
        create_ve('test-data/deploy-ve', pypi)

    def test_attributes(self):
        self.assertEqual(self.app.app, 'test')
        self.assertEqual(self.app.target, 'master')
        self.assertTrue(isinstance(self.app.repository, Repository))
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
        version = '1'
        with open(self.tmppath('test.tar.gz')) as f:
            self.repo.put('test', version, f, {'deploy_compat': '3'})
        os.unlink(self.tmppath('test.tar.gz'))

        self.app.lock()
        self.app.unpack(version)
        self.app.unlock()

        self.assertTMPPExists('srv', 'test', 'versions', version)
        self.assertTMPPExists('srv', 'test', 'versions', version, 'bar')

    def test_double_unpack(self):
        self.create_tar('test.tar.gz', 'foo/bar')
        version = '1'
        with open(self.tmppath('test.tar.gz')) as f:
            self.repo.put('test', version, f, {'deploy_compat': '3'})
        os.unlink(self.tmppath('test.tar.gz'))

        self.app.lock()
        self.app.unpack(version)
        self.app.unpack(version)
        self.app.unlock()

        self.assertTMPPExists('srv', 'test', 'versions', version)
        self.assertTMPPExists('srv', 'test', 'versions', version, 'bar')

    def test_unpack_live(self):
        self.create_tar('test.tar.gz', 'foo/bar')
        version = '1'
        with open(self.tmppath('test.tar.gz')) as f:
            self.repo.put('test', version, f, {})
        os.unlink(self.tmppath('test.tar.gz'))

        os.makedirs(self.tmppath('srv', 'test', 'versions', version))
        os.symlink(os.path.join('versions', version),
                   self.tmppath('srv', 'test', 'live'))
        self.assertEqual(self.app.live_version, version)

        self.app.lock()
        self.app.unpack(version)
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

from yodeploy.hooks.base import DeployHook


class Hooks(DeployHook):
    def prepare(self):
        open(os.path.join(self.root, 'hello'), 'w').close()


hooks = Hooks
""")
        with open(self.tmppath('srv', 'test', 'versions', 'foo', 'deploy',
                               'requirements.txt'), 'w') as f:
            f.write('yodeploy\n')
        upload_ve(self.repo, 'deploy', self._deploy_ve_hash,
                  source='test-data/deploy-ve/virtualenv.tar.gz')
        self.app.lock()
        self.app.prepare('foo')
        self.app.unlock()
        self.assertTMPPExists('srv', 'test', 'hello')

    def test_deployed(self):
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'foo', 'deploy'))
        with open(self.tmppath('srv', 'test', 'versions', 'foo', 'deploy',
                               'hooks.py'), 'w') as f:
            f.write("""import os

from yodeploy.hooks.base import DeployHook


class Hooks(DeployHook):
    def deployed(self):
        open(os.path.join(self.root, 'hello'), 'w').close()


hooks = Hooks
""")
        with open(self.tmppath('srv', 'test', 'versions', 'foo', 'deploy',
                               'requirements.txt'), 'w') as f:
            f.write('yodeploy\n')
        upload_ve(self.repo, 'deploy', self._deploy_ve_hash,
                  source='test-data/deploy-ve/virtualenv.tar.gz')
        self.app.lock()
        self.app.deployed('foo')
        self.app.unlock()
        self.assertTMPPExists('srv', 'test', 'hello')

    def test_deploy(self):
        self.create_tar('test.tar.gz', 'foo/bar', contents={
            'foo/deploy/hooks.py': """import os

from yodeploy.hooks.base import DeployHook


class Hooks(DeployHook):
    def prepare(self):
        open(os.path.join(self.root, 'hello'), 'w').close()
    def deployed(self):
        open(os.path.join(self.root, 'there'), 'w').close()


hooks = Hooks
""",
            'foo/deploy/requirements.txt': 'yodeploy\n',
        })
        version = '1'
        with open(self.tmppath('test.tar.gz')) as f:
            self.repo.put('test', version, f, {'deploy_compat': '3'})
        upload_ve(self.repo, 'deploy', self._deploy_ve_hash,
                  source='test-data/deploy-ve/virtualenv.tar.gz')
        os.unlink(self.tmppath('test.tar.gz'))

        self.app.deploy(version)
        self.assertTMPPExists('srv', 'test', 'versions', version, 'bar')
        self.assertTMPPExists('srv', 'test', 'live', 'bar')
        self.assertTMPPExists('srv', 'test', 'hello')
        self.assertTMPPExists('srv', 'test', 'there')
