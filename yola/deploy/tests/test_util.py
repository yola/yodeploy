import grp
import os
import pwd
import stat

from . import TmpDirTestCase
from ..util import chown_r, touch, LockFile, LockedException, UnlockedException


class TestUtils(TmpDirTestCase):
    def test_chown_r(self):
        self.mkdir('foo', 'bar')
        open(self.tmppath('foo', 'baz'), 'w').close()
        # We probably aren't root...
        my_user = pwd.getpwuid(os.getuid())[0]
        my_group = grp.getgrgid(os.getgid())[0]
        chown_r(self.tmppath('foo'), my_user, my_group)

    def test_touch(self):
        touch(self.tmppath('foo'))
        self.assertTMPPExists('foo')

    def test_touch_perm(self):
        touch(self.tmppath('foo'), perm=0641)
        s = os.stat(self.tmppath('foo'))
        self.assertEqual(stat.S_IMODE(s.st_mode), 0641)

    def test_touch_uid(self):
        # We probably aren't root...
        my_user = pwd.getpwuid(os.getuid())[0]
        my_group = grp.getgrgid(os.getgid())[0]
        touch(self.tmppath('foo'), user=my_user, group=my_group)
        s = os.stat(self.tmppath('foo'))
        self.assertEqual(s.st_uid, os.getuid())
        self.assertEqual(s.st_gid, os.getgid())


class LockFileTest(TmpDirTestCase):
    def test_creation_deletion(self):
        lf = LockFile(self.tmppath('lockfile'))
        lf.acquire()
        self.assertTrue(os.path.exists(self.tmppath('lockfile')))
        lf.release()
        self.assertFalse(os.path.exists(self.tmppath('lockfile')))

    def test_stale_lock(self):
        lf = LockFile(self.tmppath('lockfile'))
        open(self.tmppath('lockfile'), 'w').close()
        lf.acquire()
        lf.release()
        self.assertFalse(os.path.exists(self.tmppath('lockfile')))

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
