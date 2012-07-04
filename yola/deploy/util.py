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
