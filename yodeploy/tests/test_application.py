import os
import shutil
import time

from ..application import Application
from ..repository import LocalRepositoryStore, Repository
from ..util import LockedException
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
        self.app = Application('test', self.tmppath('config.py'))
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
        self.assertTrue(isinstance(self.app.settings, dict))
        self.assertEqual(self.app.appdir, self.tmppath('srv', 'test'))

    def test_live_version_never_deployed(self):
        self.assertTrue(self.app.live_version is None)

    def test_live_version(self):
        self.mkdir('srv', 'test', 'versions', 'foobar')
        os.symlink(os.path.join('versions', 'foobar'),
                   self.tmppath('srv', 'test', 'live'))
        self.assertEqual(self.app.live_version, 'foobar')

    def test_deployed_versions(self):
        self.mkdir('srv', 'test', 'versions', '1')
        self.mkdir('srv', 'test', 'versions', '2')
        self.mkdir('srv', 'test', 'versions', 'unpack')
        self.assertEqual(self.app.deployed_versions, ['1', '2'])

    def test_locking(self):
        with self.app.lock:
            try:
                with self.app.lock:
                    raised = False
            except LockedException:
                raised = True
        self.assertTrue(raised)

    def test_unpack(self):
        self.create_tar('test.tar.gz', 'foo/bar')
        version = '1'
        with open(self.tmppath('test.tar.gz')) as f:
            self.repo.put('test', version, f, {'deploy_compat': '3'})
        os.unlink(self.tmppath('test.tar.gz'))

        with self.app.lock:
            self.app.unpack('master', self.repo, version)

        self.assertTMPPExists('srv', 'test', 'versions', version)
        self.assertTMPPExists('srv', 'test', 'versions', version, 'bar')

    def test_double_unpack(self):
        self.create_tar('test.tar.gz', 'foo/bar')
        version = '1'
        with open(self.tmppath('test.tar.gz')) as f:
            self.repo.put('test', version, f, {'deploy_compat': '3'})
        os.unlink(self.tmppath('test.tar.gz'))

        with self.app.lock:
            self.app.unpack('master', self.repo, version)
            self.app.unpack('master', self.repo, version)

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

        with self.app.lock:
            self.app.unpack('master', self.repo, version)

    def test_swing_symlink_create(self):
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'foobar'))

        with self.app.lock:
            self.app.swing_symlink('foobar')

        self.assertTMPPExists('srv', 'test', 'live')
        self.assertEqual(self.app.live_version, 'foobar')

    def test_swing_symlink_overwrite(self):
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'foo'))
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'bar'))
        os.symlink(os.path.join('versions', 'foo'),
                   self.tmppath('srv', 'test', 'live'))

        self.assertEqual(self.app.live_version, 'foo')

        with self.app.lock:
            self.app.swing_symlink('bar')

        self.assertTMPPExists('srv', 'test', 'live')
        self.assertEqual(self.app.live_version, 'bar')

    def test_swing_symlink_stale_live_new(self):
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'foo'))
        os.makedirs(self.tmppath('srv', 'test', 'versions', 'bar'))
        os.symlink(os.path.join('versions', 'foo'),
                   self.tmppath('srv', 'test', 'live.new'))

        with self.app.lock:
            self.app.swing_symlink('bar')

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
        with open(self.tmppath('srv', 'test', 'versions', 'foo', 'deploy',
                               'compat'), 'w') as f:
            f.write('4\n')
        upload_ve(self.repo, 'deploy', self._deploy_ve_hash,
                  source='test-data/deploy-ve/virtualenv.tar.gz')
        with self.app.lock:
            self.app.prepare('master', self.repo, 'foo')
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
        with open(self.tmppath('srv', 'test', 'versions', 'foo', 'deploy',
                               'compat'), 'w') as f:
            f.write('4\n')
        upload_ve(self.repo, 'deploy', self._deploy_ve_hash,
                  source='test-data/deploy-ve/virtualenv.tar.gz')
        with self.app.lock:
            self.app.deployed('master', self.repo, 'foo')
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
            'foo/deploy/compat': '4\n',
        })
        version = '1'
        with open(self.tmppath('test.tar.gz')) as f:
            self.repo.put('test', version, f, {'deploy_compat': '3'})
        upload_ve(self.repo, 'deploy', self._deploy_ve_hash,
                  source='test-data/deploy-ve/virtualenv.tar.gz')
        os.unlink(self.tmppath('test.tar.gz'))

        self.app.deploy('master', self.repo, version)
        self.assertTMPPExists('srv', 'test', 'versions', version, 'bar')
        self.assertTMPPExists('srv', 'test', 'live', 'bar')
        self.assertTMPPExists('srv', 'test', 'hello')
        self.assertTMPPExists('srv', 'test', 'there')

    def test_gc(self):
        for version in range(10):
            self.mkdir('srv', 'test', 'versions', str(version))
        os.symlink(os.path.join('versions', '3'),
                   self.tmppath('srv', 'test', 'live'))
        # Avoid the int-env hack
        os.utime(self.tmppath('srv', 'test', 'versions', '3'), None)
        self.app.gc(2)
        self.assertEqual(self.app.deployed_versions, ['3', '8', '9'])

    def test_gc_bootstrapped_versions(self):
        self.mkdir('srv', 'test', 'versions', '1')
        self.mkdir('srv', 'test', 'versions', '1001')
        os.symlink(os.path.join('versions', '1'),
                   self.tmppath('srv', 'test', 'live'))
        earlier = int(time.time()) - 100
        os.utime(self.tmppath('srv', 'test', 'versions', '1001'),
                 (earlier, earlier))
        self.app.gc(1)
        self.assertEqual(self.app.deployed_versions, ['1'])

    def test_gc_virtualenvs(self):
        for version in range(10):
            self.mkdir('srv', 'test', 'versions', str(version))
            self.mkdir('srv', 'test', 'virtualenvs', str(version))
            os.symlink(os.path.join('..', 'virtualenvs', str(version)),
                       self.tmppath('srv', 'test', 'versions', str(version),
                                    'virtualenv'))
        self.app.gc(2)
        self.assertEqual(self.app.deployed_versions, ['8', '9'])
        self.assertEqual(
            sorted(os.listdir(self.tmppath('srv', 'test', 'virtualenvs'))),
            ['8', '9'])
