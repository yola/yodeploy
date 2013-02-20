import imp
import sys
import os


SYSTEM_DEPLOY_SETTINGS = ['/etc/yola/deploy.conf']


def load_settings(fn):
    '''Load deploy_settings from the specified filename'''
    fake_mod = '_deploy_settings'
    description = ('.py', 'r', imp.PY_SOURCE)
    with open(fn) as f:
        m = imp.load_module(fake_mod, f, fn, description)
    return m.deploy_settings


def find_deploy_config(exit_if_missing=True):
    """Search all the common locations for the deploy_settings.
    Return the location.

    If they can't be found, if exit_if_missing is set, spit out an error and
    exit Python otherwise, return None.
    """
    paths = []
    fn = 'yola.deploy.conf'
    if sys.platform.startswith('win'):
        if 'APPDATA' in os.environ:
            paths.append((os.environ['APPDATA'], fn))
        paths.append(('~', 'Local Settings', 'Application Data', fn))
    elif sys.platform == 'darwin':
        paths.append(('~', 'Library', 'Application Support', fn))
    elif sys.platform.startswith('linux'):
        if 'XDG_DATA_HOME' in os.environ:
            paths.append((os.environ['XDG_DATA_HOME'], fn))
        paths.append(('~', '.local', 'share', fn))

    paths = [os.path.expanduser(os.path.join(*path)) for path in paths]
    paths += SYSTEM_DEPLOY_SETTINGS
    for path in paths:
        if os.path.exists(path):
            return path

    if exit_if_missing:
        print >> sys.stderr, "Deploy settings couldn't be located."
        print >> sys.stderr, ("Copy yola.deploy's conf/yola.deploy.conf.sample"
                              " to %s" % paths[0])
        sys.exit(1)
