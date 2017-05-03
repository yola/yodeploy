import errno
import grp
import itertools
import os
import pwd
import stat
import subprocess
import unittest

from yodeploy.tests import (
    HelperScriptConsumer, TmpDirTestCase, yodeploy_location)
from yodeploy.util import (
    chown_r, delete_dir_content, extract_tar, ignoring, touch)


class TestChown_R(TmpDirTestCase):
    def test_simple(self):
        self.mkdir('foo', 'bar')
        open(self.tmppath('foo', 'baz'), 'w').close()
        # We probably aren't root...
        my_user = pwd.getpwuid(os.getuid())[0]
        my_group = grp.getgrgid(os.getgid())[0]
        chown_r(self.tmppath('foo'), my_user, my_group)

    def test_integer(self):
        self.mkdir('foo', 'bar')
        open(self.tmppath('foo', 'baz'), 'w').close()
        # We probably aren't root...
        my_user = os.getuid()
        my_group = -1
        chown_r(self.tmppath('foo'), my_user, my_group)


class TestTouch(TmpDirTestCase):
    def test_simple(self):
        touch(self.tmppath('foo'))
        self.assertTMPPExists('foo')

    def test_perm(self):
        touch(self.tmppath('foo'), perm=0o641)
        s = os.stat(self.tmppath('foo'))
        self.assertEqual(stat.S_IMODE(s.st_mode), 0o641)

    def test_uid(self):
        # We probably aren't root...
        my_user = pwd.getpwuid(os.getuid())[0]
        my_group = grp.getgrgid(os.getgid())[0]
        touch(self.tmppath('foo'), user=my_user, group=my_group)
        s = os.stat(self.tmppath('foo'))
        self.assertEqual(s.st_uid, os.getuid())
        self.assertEqual(s.st_gid, os.getgid())


class TestExtractTar(TmpDirTestCase, HelperScriptConsumer):
    def test_simple(self):
        self.create_tar('test.tar.gz', 'foo/bar', 'foo/baz')
        extract_tar(self.tmppath('test.tar.gz'), self.tmppath('extracted'))
        self.assertTMPPExists('extracted')
        self.assertTMPPExists('extracted/bar')
        self.assertTMPPExists('extracted/baz')

    def test_multi_root(self):
        self.create_tar('test.tar.gz', 'foo/bar', 'baz/quux')
        self.assertRaises(Exception, extract_tar, self.tmppath('test.tar.gz'),
                          self.tmppath('extracted'))
        self.assertNotTMPPExists('extracted')
        self.assertNotTMPPExists('extracted/bar')
        self.assertNotTMPPExists('extracted/quux')

    @unittest.skipIf('fakeroot' not in itertools.chain.from_iterable(
        os.listdir(component)
        for component in os.environ['PATH'].split(os.pathsep)
        if os.path.isdir(component)), "Test requires fakeroot")
    def test_permission_squash(self):
        self.create_tar('test.tar.gz', 'foo/bar')

        env = {
            'PATH': os.environ['PATH'],
            'PYTHONPATH': yodeploy_location(),
        }

        subprocess.check_call((
            'fakeroot',
            'python',
            self.get_helper_path('permission_squash_checker.py'),
            self.tmppath('test.tar.gz'),
            self.tmppath('extracted'),
            self.tmppath('extracted/bar')
        ), env=env)


class TestDelete_Dir_Content(TmpDirTestCase):
    def test_simple(self):
        f = self.tmppath('test.txt')
        touch(f)
        d = self.mkdir('foo', 'bar')
        self.assertTrue(os.path.exists(f))
        self.assertTrue(os.path.exists(d))
        delete_dir_content(self.tmppath())
        self.assertFalse(os.path.exists(f))
        self.assertFalse(os.path.exists(d))


class TestContextManagerForIgnoringErrors(TmpDirTestCase):
    def test_can_be_used_to_create_directories(self):
        d = self.tmppath('some', 'dir')
        self.assertFalse(os.path.exists(d))
        with ignoring(errno.EEXIST):
            os.makedirs(d)
        self.assertTrue(os.path.exists(d))
        with ignoring(errno.EEXIST):
            os.makedirs(d)
