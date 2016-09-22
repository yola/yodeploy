import errno
import fcntl
import logging
import os
import time

log = logging.getLogger(__name__)


class LockedException(Exception):
    pass


class UnlockedException(Exception):
    pass


class LockFile(object):
    """A simple on-disk Unix lock file.
    Automatically cleans up stale lock files.
    """
    def __init__(self, filename):
        self.filename = filename
        self._f = None

    def acquire(self):
        if not self.try_acquire():
            raise LockedException("Lock unavailable")

    def try_acquire(self):
        """
        Attempt to acquire the lock. Returns boolean result
        """
        try:
            self._f = os.open(self.filename,
                              os.O_EXCL | os.O_CREAT | os.O_WRONLY, 0o600)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
            self._f = os.open(self.filename, os.O_WRONLY)
        try:
            fcntl.flock(self._f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            return False
        return True

    @property
    def held(self):
        return self._f is not None

    def release(self):
        if not self.held:
            raise UnlockedException("We don't hold a lock")
        fcntl.flock(self._f, fcntl.LOCK_UN)
        os.unlink(self.filename)
        os.close(self._f)
        self._f = None

    def __enter__(self):
        self.acquire()

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()


class SpinLockFile(LockFile):
    """
    A LockFile that will spin up to timeout seconds
    """
    def __init__(self, filename, timeout):
        self.timeout = timeout
        super(SpinLockFile, self).__init__(filename)

    def acquire(self):
        start_time = time.time()
        logged = False
        while time.time() - start_time < self.timeout:
            if self.try_acquire():
                break
            if not logged:
                log.debug("Lock unavialible, retrying for %i seconds...",
                          self.timeout)
                logged = True
            time.sleep(0.1)
        else:
            raise LockedException("Lock unavailable. Timed out waiting.")
