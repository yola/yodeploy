import errno
import os
import subprocess
import shutil
import sys

from os.path import join

from yodeploy.deploy import deploy
from yodeploy.tests import deployconf

tests_dir = os.path.join(os.path.dirname(__file__), '..')
bin_dir = os.path.join(tests_dir, '..', 'cmds')
deployconf_fn = deployconf.__file__.rstrip('c')


def rmdir(path):
    try:
        shutil.rmtree(path)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise


def clear(app_name):
    store = deployconf.deploy_settings.artifacts.store_settings.local.directory
    rmdir(join(store, app_name))
    rmdir(join(deployconf.deploy_settings.paths.apps, app_name))


def build_sample(app_name, version='1'):
    """Calls build_artifact in the sample app."""
    script_path = os.path.join(bin_dir, 'build_artifact.py')
    app_dir = os.path.join(tests_dir, 'samples', app_name)
    env = {
        'PATH': os.environ['PATH'],
        'PYTHONPATH': ':'.join(sys.path),
        'BUILD_NUMBER': version,
        'YOLA_SRC': os.path.join(tests_dir, 'samples')
    }
    p = subprocess.Popen(
        (script_path, '--no-virtualenvs', '--config', deployconf_fn),
        cwd=app_dir,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env)
    out, err = p.communicate()
    if err:
        print out
        print err
    assert err == ""
    assert p.wait() == 0


def deploy_sample(app_name, version="1"):
    """Deploys the sample app to tests/filesys/deployed/app_name/."""
    args = {
        'app': app_name,
        'target': 'master',
        'config': deployconf_fn,
        'version': version,
        'deploy_settings': deployconf.deploy_settings
    }
    deploy(**args)
