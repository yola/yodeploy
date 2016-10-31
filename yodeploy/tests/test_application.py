import os
import shutil
import tarfile
import time

from yodeploy.application import Application
from yodeploy.locking import LockedException
from yodeploy.repository import LocalRepositoryStore, Repository
from yodeploy.tests import TmpDirTestCase
from yodeploy.virtualenv import create_ve, sha224sum, upload_ve, ve_version

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures/')


class ApplicationTestCase(TmpDirTestCase):
    def setUp(self):
        super(ApplicationTestCase, self).setUp()

        shutil.copy(
            os.path.join(FIXTURES_DIR, 'config.py'), self.tmppath('config.py'))

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


class ApplicationTest(ApplicationTestCase):
    def setUp(self):
        super(ApplicationTest, self).setUp()

        sample_app = os.path.join(FIXTURES_DIR, 'simple_sample_app')

        # Simulate multiple installed versions of the sample app fixture.
        shutil.copytree(
            sample_app, self.tmppath('srv', 'test', 'versions', 'foo'))
        shutil.copytree(
            sample_app, self.tmppath('srv', 'test', 'versions', 'bar'))

    def test_attributes(self):
        self.assertEqual(self.app.app, 'test')
        self.assertTrue(isinstance(self.app.settings, dict))
        self.assertEqual(self.app.appdir, self.tmppath('srv', 'test'))

    def test_live_version_never_deployed(self):
        self.assertTrue(self.app.live_version is None)

    def test_live_version(self):
        os.symlink(os.path.join('versions', 'bar'),
                   self.tmppath('srv', 'test', 'live'))
        self.assertEqual(self.app.live_version, 'bar')

    def test_deployed_versions(self):
        self.mkdir('srv', 'test', 'versions', 'unpack')
        self.assertEqual(self.app.deployed_versions, ['bar', 'foo'])

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
        with self.app.lock:
            self.app.swing_symlink('bar')

        self.assertTMPPExists('srv', 'test', 'live')
        self.assertEqual(self.app.live_version, 'bar')

    def test_swing_symlink_overwrite(self):
        os.symlink(os.path.join('versions', 'foo'),
                   self.tmppath('srv', 'test', 'live'))

        self.assertEqual(self.app.live_version, 'foo')

        with self.app.lock:
            self.app.swing_symlink('bar')

        self.assertTMPPExists('srv', 'test', 'live')
        self.assertEqual(self.app.live_version, 'bar')

    def test_swing_symlink_stale_live_new(self):
        os.symlink(os.path.join('versions', 'foo'),
                   self.tmppath('srv', 'test', 'live.new'))

        with self.app.lock:
            self.app.swing_symlink('bar')

        self.assertTMPPExists('srv', 'test', 'live')
        self.assertNotTMPPExists('srv', 'test', 'live.new')
        self.assertEqual(self.app.live_version, 'bar')

    def test_prepare_hook(self):
        upload_ve(self.repo, 'deploy', self._deploy_ve_hash,
                  source='test-data/deploy-ve/virtualenv.tar.gz')
        with self.app.lock:
            self.app.prepare('master', self.repo, 'foo')
        self.assertTMPPExists('srv', 'test', 'prepare_hook_output')

    def test_deployed(self):
        upload_ve(self.repo, 'deploy', self._deploy_ve_hash,
                  source='test-data/deploy-ve/virtualenv.tar.gz')
        with self.app.lock:
            self.app.deployed('master', self.repo, 'foo')
        self.assertTMPPExists('srv', 'test', 'deployed_hook_output')

    def test_deploy(self):
        with tarfile.open(self.tmppath('test.tar.gz'), 'w:gz') as tar:
            tar.add(
                os.path.join(FIXTURES_DIR, 'simple_sample_app'), arcname='foo')

        version = '1'
        with open(self.tmppath('test.tar.gz')) as f:
            self.repo.put('test', version, f, {'deploy_compat': '3'})
        upload_ve(self.repo, 'deploy', self._deploy_ve_hash,
                  source='test-data/deploy-ve/virtualenv.tar.gz')
        os.unlink(self.tmppath('test.tar.gz'))

        self.app.deploy('master', self.repo, version)
        self.assertTMPPExists('srv', 'test', 'versions', version, 'bar')
        self.assertTMPPExists('srv', 'test', 'live', 'bar')
        self.assertTMPPExists('srv', 'test', 'prepare_hook_output')
        self.assertTMPPExists('srv', 'test', 'deployed_hook_output')


class ApplicationGCTests(ApplicationTestCase):
    """Application.gc()"""
    def setUp(self):
        super(ApplicationGCTests, self).setUp()

        # Simulate 10 installs with version 3 as the live version.
        for version in range(10):
            self.mkdir('srv', 'test', 'versions', str(version))
            self.mkdir('srv', 'test', 'virtualenvs', str(version))
            os.symlink(os.path.join('..', 'virtualenvs', str(version)),
                       self.tmppath('srv', 'test', 'versions', str(version),
                                    'virtualenv'))

        os.symlink(
            os.path.join('versions', '3'), self.tmppath('srv', 'test', 'live'))

        # Avoid the int-env hack
        os.utime(self.tmppath('srv', 'test', 'versions', '3'), None)

    def test_prunes_all_but_latest_installs_and_live_version(self):
        self.app.gc(2)
        self.assertEqual(self.app.deployed_versions, ['3', '8', '9'])

    def test_prunes_installs_versioned_higher_than_live_if_older_mtime(self):
        self.mkdir('srv', 'test', 'versions', '1001')
        earlier = int(time.time()) - 100
        os.utime(self.tmppath('srv', 'test', 'versions', '1001'),
                 (earlier, earlier))
        self.app.gc(1)
        self.assertEqual(self.app.deployed_versions, ['3'])

    def test_prunes_all_but_latest_venvs_and_live_versions_venv(self):
        self.app.gc(2)
        self.assertEqual(
            sorted(os.listdir(self.tmppath('srv', 'test', 'virtualenvs'))),
            ['3', '8', '9'])
