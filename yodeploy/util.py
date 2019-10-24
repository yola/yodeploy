"""Yodeploy utilities."""
import contextlib
import grp
import logging
import os
import pwd
import shutil
import sys
import tarfile

log = logging.getLogger(__name__)


def chown_r(path, user, group):
    """Recursive chown."""
    uid = user if isinstance(user, int) else pwd.getpwnam(user).pw_uid
    gid = group if isinstance(group, int) else grp.getgrnam(group).gr_gid

    for root, dirs, files in os.walk(path):
        os.chown(root, uid, gid)
        for fn in files:
            os.lchown(os.path.join(root, fn), uid, gid)


def touch(path, user=None, group=None, perm=None):
    """Create a file owned by user.group with the specified permissions."""
    open(path, 'a').close()

    uid = pwd.getpwnam(user).pw_uid if user else -1
    gid = grp.getgrnam(group).gr_gid if group else -1
    os.chown(path, uid, gid)

    if perm:
        os.chmod(path, perm)


def extract_tar(tarball, root):
    """Ensure that tarball only has one root directory.

    Extract it into the parent directory of root, and rename the extracted
    directory to root.
    """
    workdir = os.path.dirname(root)
    if sys.version_info[0] < 3:
        workdir = workdir.encode(sys.getfilesystemencoding())
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
    """Delete all files and directories under given path."""
    for root, dirs, files in os.walk(path):
        for f in files:
            try:
                os.unlink(os.path.join(root, f))
            except OSError:
                log.warn("Unable to delete %s %s", root, f)
        for d in dirs:
            try:
                shutil.rmtree(os.path.join(root, d))
            except OSError:
                log.warn("Unable to delete %s %s", root, d)


@contextlib.contextmanager
def ignoring(ignore_err_no):
    """Ignore OSErrors accoring to the given error number."""
    try:
        yield
    except OSError as e:
        if e.errno != ignore_err_no:
            raise


def infer_compat_version():
    """Return appropriate compat level for the python version"""
    major_version_to_compat = {
        2: 4,
        3: 5,
    }
    return major_version_to_compat[sys.version_info.major]
