from StringIO import StringIO

from ..repository import version_sort_key, RepositoryFile, LocalRepository
from . import unittest, TmpDirTestCase


class TestVersionSortKey(unittest.TestCase):
    def test_digits(self):
        unsorted = ['1', '10', '2']
        expected = ['1', '2', '10']
        unsorted.sort(key=version_sort_key)
        self.assertEqual(unsorted, expected)

    def test_alpha(self):
        unsorted = ['c', 'ba', 'b']
        expected = ['b', 'ba', 'c']
        unsorted.sort(key=version_sort_key)
        self.assertEqual(unsorted, expected)

    def test_mixed(self):
        unsorted = ['abc', 'a1b', 'a10b', 'a2b', 'a1', 'abc1']
        expected = ['a1', 'a1b', 'a2b', 'a10b', 'abc', 'abc1']
        unsorted.sort(key=version_sort_key)
        self.assertEqual(unsorted, expected)


class TestRepositoryFile(unittest.TestCase):
    def test_read(self):
        f = open(__file__)
        wrapped = RepositoryFile(f, {})
        self.assertTrue('some random string' in wrapped.read())
        f.close()

    def test_context_manager(self):
        f = open(__file__)
        with RepositoryFile(f, {}) as wrapped:
            self.assertTrue('some random string' in wrapped.read())
        self.assertRaises(ValueError, f.read)


class TestLocalRepository(TmpDirTestCase):
    def setUp(self):
        super(TestLocalRepository, self).setUp()
        self.repo = LocalRepository(self.mkdir('repo'))

    def assertContents(self, contents, *fragments):
        with open(self.tmppath(*fragments)) as f:
            self.assertEqual(f.read(), contents)

    def test_init_nonexistent(self):
        self.assertRaises(Exception, LocalRepository, self.tmppath('missing'))

    def test_initial_store(self):
        self.repo.store('foo', '1.0', StringIO('data'), {})
        self.assertContents('data',
                'repo', 'foo', 'master', 'foo.tar.gz', '1.0')

    def test_store_latest(self):
        self.repo.store('foo', '1.0', StringIO('version 1'), {})
        self.assertContents('1.0\n',
                'repo', 'foo', 'master', 'foo.tar.gz', 'latest')
        self.repo.store('foo', '2.0', StringIO('version 2'), {})
        self.assertContents('2.0\n',
                'repo', 'foo', 'master', 'foo.tar.gz', 'latest')

    def test_store_illegal_versions(self):
        self.assertRaises(ValueError, self.repo.store, 'foo', 'latest',
                          StringIO('version 1'), {})

    def test_meta(self):
        self.repo.store('foo', '1.0', StringIO('data'), {'bar': 'baz'})
        with self.repo.get('foo') as f:
            self.assertEqual(f.metadata, {'bar': 'baz'})

    def test_get(self):
        self.repo.store('foo', '1.0', StringIO('data'), {})
        with self.repo.get('foo', '1.0') as f:
            self.assertEqual(f.read(), 'data')

    def test_get_latest(self):
        self.repo.store('foo', '1.0', StringIO('old data'), {})
        self.repo.store('foo', '2.0', StringIO('new data'), {})
        with self.repo.get('foo') as f:
            self.assertEqual(f.read(), 'new data')

    def test_get_missing(self):
        self.repo.store('foo', '1.0', StringIO('old data'), {})
        self.assertRaises(KeyError, self.repo.get, 'foo', '2.0')

    def test_targets(self):
        self.repo.store('foo', '1.0', StringIO('master data'), {})
        self.repo.store('foo', '2.0', StringIO('dev data'), {}, 'dev')
        with self.repo.get('foo') as f:
            self.assertEqual(f.read(), 'master data')
        with self.repo.get('foo', target='dev') as f:
            self.assertEqual(f.read(), 'dev data')

    def test_list_apps(self):
        self.assertFalse(self.repo.list_apps())
        self.repo.store('foo', '1.0', StringIO('data'), {})
        self.assertEqual(self.repo.list_apps(), ['foo'])

    def test_list_targets(self):
        self.assertFalse(self.repo.list_targets('foo'))
        self.repo.store('foo', '1.0', StringIO('data'), {})
        self.assertEqual(self.repo.list_targets('foo'), ['master'])

    def test_list_artifacts(self):
        self.assertFalse(self.repo.list_artifacts('foo'))
        self.repo.store('foo', '1.0', StringIO('data'), {})
        self.assertEqual(self.repo.list_artifacts('foo'), ['foo.tar.gz'])

    def test_list_versions(self):
        self.assertFalse(self.repo.list_versions('foo'))
        self.repo.store('foo', '1.0', StringIO('data'), {})
        self.assertEqual(self.repo.list_versions('foo'), ['1.0'])

    def test_delete(self):
        self.repo.store('foo', '1.0', StringIO('data'), {})
        self.repo.delete('foo', '1.0')
        self.assertFalse(self.repo.list_versions('foo'))
        self.assertNotTMPPExists('repo', 'foo', 'master', 'foo.tar.gz',
                                 'latest')

    def test_delete_older(self):
        self.repo.store('foo', '1.0', StringIO('old data'), {})
        self.repo.store('foo', '2.0', StringIO('new data'), {})

        self.repo.delete('foo', '1.0')

        self.assertEqual(self.repo.list_versions('foo'), ['2.0'])
        with self.repo.get('foo') as f:
            self.assertEqual(f.read(), 'new data')

    def test_delete_latest(self):
        self.repo.store('foo', '1.0', StringIO('old data'), {})
        self.assertContents('1.0\n',
                'repo', 'foo', 'master', 'foo.tar.gz', 'latest')
        self.repo.store('foo', '2.0', StringIO('new data'), {})

        self.repo.delete('foo', '2.0')

        self.assertContents('1.0\n',
                'repo', 'foo', 'master', 'foo.tar.gz', 'latest')
        with self.repo.get('foo') as f:
            self.assertEqual(f.read(), 'old data')

    def test_delete_missing_app(self):
        self.assertRaises(ValueError, self.repo.delete, 'foo', '1.0')

    def test_delete_missing_version(self):
        self.repo.store('foo', '1.0', StringIO('data'), {})
        self.assertRaises(ValueError, self.repo.delete, 'foo', '2.0')

    def test_gc(self):
        self.repo.store('foo', '1.0', StringIO('data'), {})
        self.repo.store('foo', '2.0', StringIO('data'), {})
        self.repo.store('foo', '3.0', StringIO('data'), {})
        self.repo.store('foo', '4.0', StringIO('data'), {})
        self.repo.store('foo', '3.1', StringIO('data'), {}, 'dev')
        self.repo.store('foo', '4.1', StringIO('data'), {}, 'dev')
        self.repo.gc(2)
        self.assertEqual(self.repo.list_versions('foo'), ['3.0', '4.0'])
        self.assertEqual(self.repo.list_versions('foo', 'dev'), ['3.1', '4.1'])
