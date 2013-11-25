import errno
import fcntl
import grp
import os
import pwd
import shutil
import tarfile


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
        try:
            self._f = os.open(self.filename,
                              os.O_EXCL | os.O_CREAT | os.O_WRONLY, 0600)
        except OSError, e:
            if e.errno != errno.EEXIST:
                raise
            self._f = os.open(self.filename, os.O_WRONLY)
        try:
            fcntl.flock(self._f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError:
            raise LockedException("Lock unavailable")

    def release(self):
        if self._f is None:
            raise UnlockedException("We don't hold a lock")
        fcntl.flock(self._f, fcntl.LOCK_UN)
        os.unlink(self.filename)
        os.close(self._f)
        self._f = None


def chown_r(path, user, group):
    '''recursive chown'''
    uid = user if isinstance(user, int) else pwd.getpwnam(user).pw_uid
    gid = group if isinstance(group, int) else grp.getgrnam(group).gr_gid

    for root, dirs, files in os.walk(path):
        os.chown(root, uid, gid)
        for fn in files:
            os.chown(os.path.join(root, fn), uid, gid)


def touch(path, user=None, group=None, perm=None):
    '''Create a file owned by user.group with the specified permissions'''

    open(path, 'a').close()

    uid = pwd.getpwnam(user).pw_uid if user else -1
    gid = grp.getgrnam(group).gr_gid if group else -1
    os.chown(path, uid, gid)

    if perm:
        os.chmod(path, perm)


def extract_tar(tarball, root):
    '''Ensure that tarball only has one root directory.
    Extract it into the parent directory of root, and rename the extracted
    directory to root.
    '''
    workdir = os.path.dirname(root)
    tar = tarfile.open(tarball, 'r')
    try:
        members = tar.getmembers()
        for member in members:
            member.uid = 0
            member.gid = 0
            member.uname = 'root'
            member.gname = 'root'
        roots = set(member.name.split('/', 1)[0] for member in members)
        if len(roots) > 1:
            raise ValueError("Tarball has > 1 top-level directory")
        tar.extractall(workdir, members)
    finally:
        tar.close()

    extracted_root = os.path.join(workdir, list(roots)[0])
    os.rename(extracted_root, root)


def delete_dir_content(path):
    '''Delete all files and directories under given path.'''
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                os.unlink(os.path.join(root, f))
            except OSError:
                print "Unable to delete %s %s" % (root, f)
        for d in dirs:
            try:
                shutil.rmtree(os.path.join(root, d))
            except OSError:
                print "Unable to delete %s %s" % (root, d)
