from io import BytesIO, StringIO
import unittest

from yodeploy.repository import (version_sort_key, RepositoryFile, Repository,
                                 LocalRepositoryStore)
from yodeploy.tests import TmpDirTestCase


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


class TestLocalRepositoryStore(TmpDirTestCase):
    def setUp(self):
        super(TestLocalRepositoryStore, self).setUp()
        self.store = LocalRepositoryStore(self.mkdir('repo'))

    def test_init_nonexistent(self):
        self.assertRaises(Exception, LocalRepositoryStore,
                          self.tmppath('missing'))

    def test_get(self):
        with open(self.tmppath('repo', 'foo'), 'w') as f:
            f.write('bar')
        with self.store.get('foo') as f:
            self.assertEqual(f.read().decode(), 'bar')

    def test_get_metadata(self):
        with open(self.tmppath('repo', 'foo'), 'w') as f:
            f.write('bar')
        with open(self.tmppath('repo', 'foo.meta'), 'w') as f:
            f.write('{"baz": "quux"}')

        meta = self.store.get_metadata('foo')
        self.assertEqual(meta, {'baz': 'quux'})

    def test_get_w_meta(self):
        with open(self.tmppath('repo', 'foo'), 'w') as f:
            f.write('bar')
        with open(self.tmppath('repo', 'foo.meta'), 'w') as f:
            f.write('{"baz": "quux"}')

        f, meta = self.store.get('foo', True)
        try:
            self.assertEqual(f.read().decode(), 'bar')
            self.assertEqual(meta, {'baz': 'quux'})
        finally:
            f.close()

    def test_get_missing_meta(self):
        with open(self.tmppath('repo', 'foo'), 'w') as f:
            f.write('bar')

        f, meta = self.store.get('foo', True)
        try:
            self.assertEqual(f.read().decode(), 'bar')
            self.assertEqual(meta, {})
        finally:
            f.close()

    def test_put(self):
        self.store.put('foo', 'bar')
        self.assertTMPPContents('bar', 'repo', 'foo')
        self.assertNotTMPPExists('repo', 'foo.meta')

    def test_can_put_in_memory_byte_stream(self):
        self.store.put('foo', BytesIO(b'bar'))
        self.assertTMPPContents('bar', 'repo', 'foo')

    def test_can_put_in_memory_unicode_stream(self):
        self.store.put('foo', StringIO(u'bar'))
        self.assertTMPPContents('bar', 'repo', 'foo')

    def test_can_put_unicode_string(self):
        self.store.put('foo', u'unicode bar')
        self.assertTMPPContents('unicode bar', 'repo', 'foo')

    def test_can_put_byte_string(self):
        self.store.put('foo', b'bytes bar')
        self.assertTMPPContents('bytes bar', 'repo', 'foo')

    def test_can_put_unicode_mode_fp(self):
        with open(self.tmppath('test'), 'w+') as f:
            f.write(u'some unicode string')
            f.seek(0)
            self.store.put('foo', f)

        self.assertTMPPContents('some unicode string', 'repo', 'foo')

    def test_can_put_binary_mode_fp(self):
        with open(self.tmppath('test'), 'w+b') as f:
            f.write(b'some byte data')
            f.seek(0)
            self.store.put('foo', f)

        self.assertTMPPContents('some byte data', 'repo', 'foo')

    def test_put_meta(self):
        self.store.put('foo', 'bar', {'baz': 'quux'})
        self.assertTMPPContents('bar', 'repo', 'foo')
        self.assertTMPPContents('{"baz": "quux"}', 'repo', 'foo.meta')

    def test_delete(self):
        self.store.put('foo', 'bar')
        self.store.delete('foo')

    def test_delete_missing(self):
        self.assertRaises(KeyError, self.store.delete, 'foo')

    def test_delete_meta(self):
        self.store.put('foo', 'bar', {'baz': 'quux'})
        self.store.delete('foo', metadata=True)

    def test_delete_missing_meta(self):
        self.store.put('foo', 'bar')
        # Error is ignored
        self.store.delete('foo', metadata=True)

    def test_list(self):
        with open(self.tmppath('repo', 'foo'), 'w') as f:
            f.write('quux')
        with open(self.tmppath('repo', 'bar'), 'w') as f:
            f.write('quux')
        self.mkdir('repo', 'baz')
        self.assertEqual(sorted(self.store.list()), ['baz'])
        self.assertEqual(sorted(self.store.list(files=True)),
                         ['bar', 'baz', 'foo'])
        self.assertEqual(sorted(self.store.list(files=True, dirs=False)),
                         ['bar', 'foo'])


class TestLocalRepository(TmpDirTestCase):
    '''Integration test: A localRepositoryStore backed Repository'''
    def setUp(self):
        super(TestLocalRepository, self).setUp()
        store = LocalRepositoryStore(self.mkdir('repo'))
        self.repo = Repository(store)

    def test_initial_put(self):
        self.repo.put('foo', '1.0', 'data', {})
        self.assertTMPPContents('data',
                'repo', 'foo', 'master', 'foo.tar.gz', '1.0')

    def test_store_latest(self):
        self.repo.put('foo', '1.0', 'version 1', {})
        self.assertTMPPContents('1.0\n',
                'repo', 'foo', 'master', 'foo.tar.gz', 'latest')
        self.repo.put('foo', '2.0', 'version 2', {})
        self.assertTMPPContents('2.0\n',
                'repo', 'foo', 'master', 'foo.tar.gz', 'latest')

    def test_store_illegal_versions(self):
        self.assertRaises(ValueError, self.repo.put, 'foo', 'latest',
                          'version 1', {})

    def test_meta(self):
        self.repo.put('foo', '1.0', 'data', {'bar': 'baz'})
        with self.repo.get('foo') as f:
            self.assertEqual(f.metadata, {'bar': 'baz'})

    def test_get(self):
        self.repo.put('foo', '1.0', 'data', {})
        with self.repo.get('foo', '1.0') as f:
            self.assertEqual(f.read().decode(), 'data')

    def test_get_latest(self):
        self.repo.put('foo', '1.0', 'old data', {})
        self.repo.put('foo', '2.0', 'new data', {})
        with self.repo.get('foo') as f:
            self.assertEqual(f.read().decode(), 'new data')

    def test_get_missing(self):
        self.repo.put('foo', '1.0', 'old data', {})
        self.assertRaises(KeyError, self.repo.get, 'foo', '2.0')

    def test_get_metadata(self):
        self.repo.put('foo', '1.0', 'data', {'foo': 'bar'})
        self.assertEqual(self.repo.get_metadata('foo', '1.0'), {'foo': 'bar'})

    def test_latest_version(self):
        self.repo.put('foo', '1.0', 'old data', {})
        self.assertEqual(self.repo.latest_version('foo'), '1.0')
        self.repo.put('foo', '2.0', 'new data', {})
        self.assertEqual(self.repo.latest_version('foo'), '2.0')

    def test_targets(self):
        self.repo.put('foo', '1.0', 'master data', {})
        self.repo.put('foo', '2.0', 'dev data', {}, 'dev')
        with self.repo.get('foo') as f:
            self.assertEqual(f.read().decode(), 'master data')
        with self.repo.get('foo', target='dev') as f:
            self.assertEqual(f.read().decode(), 'dev data')

    def test_list_apps(self):
        self.assertFalse(self.repo.list_apps())
        self.repo.put('foo', '1.0', 'data', {})
        self.assertEqual(self.repo.list_apps(), ['foo'])

    def test_list_targets(self):
        self.assertFalse(self.repo.list_targets('foo'))
        self.repo.put('foo', '1.0', 'data', {})
        self.assertEqual(self.repo.list_targets('foo'), ['master'])

    def test_list_artifacts(self):
        self.assertFalse(self.repo.list_artifacts('foo'))
        self.repo.put('foo', '1.0', 'data', {})
        self.assertEqual(self.repo.list_artifacts('foo'), ['foo.tar.gz'])

    def test_list_versions(self):
        self.assertFalse(self.repo.list_versions('foo'))
        self.repo.put('foo', '1.0', 'data', {})
        self.assertEqual(self.repo.list_versions('foo'), ['1.0'])

    def test_delete(self):
        self.repo.put('foo', '1.0', 'data', {})
        self.repo.delete('foo', '1.0')
        self.assertFalse(self.repo.list_versions('foo'))
        self.assertNotTMPPExists('repo', 'foo', 'master', 'foo.tar.gz',
                                 'latest')

    def test_delete_older(self):
        self.repo.put('foo', '1.0', 'old data', {})
        self.repo.put('foo', '2.0', 'new data', {})

        self.repo.delete('foo', '1.0')

        self.assertEqual(self.repo.list_versions('foo'), ['2.0'])
        with self.repo.get('foo') as f:
            self.assertEqual(f.read().decode(), 'new data')

    def test_delete_latest(self):
        self.repo.put('foo', '1.0', 'old data', {})
        self.assertTMPPContents(
            '1.0\n', 'repo', 'foo', 'master', 'foo.tar.gz', 'latest')
        self.repo.put('foo', '2.0', 'new data', {})

        self.repo.delete('foo', '2.0')

        self.assertTMPPContents(
            '1.0\n', 'repo', 'foo', 'master', 'foo.tar.gz', 'latest')
        with self.repo.get('foo') as f:
            self.assertEqual(f.read().decode(), 'old data')

    def test_delete_missing_app(self):
        self.assertRaises(ValueError, self.repo.delete, 'foo', '1.0')

    def test_delete_missing_version(self):
        self.repo.put('foo', '1.0', 'data', {})
        self.assertRaises(ValueError, self.repo.delete, 'foo', '2.0')

    def test_gc(self):
        self.repo.put('foo', '1.0', 'data', {})
        self.repo.put('foo', '2.0', 'data', {})
        self.repo.put('foo', '3.0', 'data', {})
        self.repo.put('foo', '4.0', 'data', {})
        self.repo.put('foo', '3.1', 'data', {}, 'dev')
        self.repo.put('foo', '4.1', 'data', {}, 'dev')
        self.repo.gc(2)
        self.assertEqual(self.repo.list_versions('foo'), ['3.0', '4.0'])
        self.assertEqual(self.repo.list_versions('foo', 'dev'), ['3.1', '4.1'])
