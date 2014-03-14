import threading

from . import TmpDirTestCase
from ..locking import (LockFile, LockedException, SpinLockFile,
                       UnlockedException)


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

    def test_context_manager(self):
        lf = LockFile(self.tmppath('lockfile'))
        self.assertFalse(lf.held)
        with lf:
            self.assertTrue(lf.held)
        self.assertFalse(lf.held)

    def test_nested_context_manager(self):
        lf = LockFile(self.tmppath('lockfile'))
        with lf:
            self.assertRaises(LockedException, lf.acquire)


class SpinLockFileTest(TmpDirTestCase):
    def test_retries(self):
        lf = LockFile(self.tmppath('lockfile'))
        lf.acquire()
        threading.Timer(0.2, lf.release).start()

        slf = SpinLockFile(self.tmppath('lockfile'), timeout=0.5)

        self.assertTrue(lf.held)
        slf.acquire()
        self.assertFalse(lf.held)

    def test_times_out(self):
        lf = LockFile(self.tmppath('lockfile'))
        lf.acquire()

        slf = SpinLockFile(self.tmppath('lockfile'), timeout=0.2)
        self.assertRaises(LockedException, slf.acquire)
