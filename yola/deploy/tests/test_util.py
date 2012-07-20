import grp
import os
import pwd
import stat

from . import TmpDirTestCase
from ..util import (LockFile, LockedException, UnlockedException, chown_r,
                    touch, extract_tar)


class LockFileTest(TmpDirTestCase):
    def test_creation_deletion(self):
        lf = LockFile(self.tmppath('lockfile'))
        lf.acquire()
        self.assertTMPPExists('lockfile')
        lf.release()
        self.assertNotTMPPExists('lockfile')

    def test_stale_lock(self):
        lf = LockFile(self.tmppath('lockfile'))
        open(self.tmppath('lockfile'), 'w').close()
        lf.acquire()
        lf.release()
        self.assertNotTMPPExists('lockfile')

    def test_already_acquired(self):
        lf = LockFile(self.tmppath('lockfile'))
        lf.acquire()
        self.assertRaises(LockedException, lf.acquire)
        lf.release()

    def test_already_released(self):
        lf = LockFile(self.tmppath('lockfile'))
        self.assertRaises(UnlockedException, lf.release)
        lf.acquire()
        lf.release()
        self.assertRaises(UnlockedException, lf.release)

    def test_duelling(self):
        lf1 = LockFile(self.tmppath('lockfile'))
        lf2 = LockFile(self.tmppath('lockfile'))
        lf1.acquire()
        self.assertRaises(LockedException, lf2.acquire)
        lf1.release()
        lf2.acquire()
        self.assertRaises(LockedException, lf1.acquire)
        lf2.release()

    def test_uprooted(self):
        lf = LockFile(self.tmppath('foo/lockfile'))
        self.assertRaises(OSError, lf.acquire)


class TestChown_R(TmpDirTestCase):
    def test_simple(self):
        self.mkdir('foo', 'bar')
        open(self.tmppath('foo', 'baz'), 'w').close()
        # We probably aren't root...
        my_user = pwd.getpwuid(os.getuid())[0]
        my_group = grp.getgrgid(os.getgid())[0]
        chown_r(self.tmppath('foo'), my_user, my_group)


class TestTouch(TmpDirTestCase):
    def test_simple(self):
        touch(self.tmppath('foo'))
        self.assertTMPPExists('foo')

    def test_perm(self):
        touch(self.tmppath('foo'), perm=0641)
        s = os.stat(self.tmppath('foo'))
        self.assertEqual(stat.S_IMODE(s.st_mode), 0641)

    def test_uid(self):
        # We probably aren't root...
        my_user = pwd.getpwuid(os.getuid())[0]
        my_group = grp.getgrgid(os.getgid())[0]
        touch(self.tmppath('foo'), user=my_user, group=my_group)
        s = os.stat(self.tmppath('foo'))
        self.assertEqual(s.st_uid, os.getuid())
        self.assertEqual(s.st_gid, os.getgid())


class TestExtractTar(TmpDirTestCase):
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
