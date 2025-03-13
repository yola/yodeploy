# This should be self-contained, local-bootstrap imports it

import importlib.util
import sys
import os


SYSTEM_DEPLOY_SETTINGS = ['/etc/yola/deploy.conf.py']


def load_settings(fn):
    fake_mod = '_deploy_settings'
    spec = importlib.util.spec_from_file_location(fake_mod, fn)
    if spec is None:
        raise ImportError('Could not load module from %s' % fn)

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.deploy_settings


def find_deploy_config(exit_if_missing=True):
    """Search all the common locations for the deploy_settings.
    Return the location.

    If they can't be found, if exit_if_missing is set, spit out an error and
    exit Python otherwise, return None.
    """

    paths = deploy_config_paths()
    for path in paths:
        if os.path.exists(path):
            return path
    if exit_if_missing:
        print("Deploy settings couldn't be located.", file=sys.stderr)
        print("Copy yodeploy's conf/yodeploy.conf.sample to %s" % paths[0],
              file=sys.stderr)
        sys.exit(1)


def deploy_config_paths():
    '''Return all the potential paths for deploy_settings'''
    paths = []
    fn = 'yodeploy.conf.py'
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
    return paths
