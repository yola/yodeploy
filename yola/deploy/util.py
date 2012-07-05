import grp
import os
import pwd


def chown_r(path, user, group):
    '''recursive chown'''
    uid = pwd.getpwnam(user).pw_uid
    gid = grp.getgrpnam(group).gr_gid

    for root, dirs, files in os.walk(path):
        os.chown(root, uid, gid)
        for fn in files:
            os.chown(os.path.join(root, fn), uid, gid)


def touch(path, user=None, group=None, perm=None):
    '''Create a file owned by user.group with the specified permissions'''

    open(path, 'a').close()

    uid = pwd.getpwnam(user).pw_uid if user else -1
    gid = grp.getgrpnam(group).gr_gid if group else -1
    os.chown(path, uid, gid)

    if perm:
        os.chmod(path, perm)
