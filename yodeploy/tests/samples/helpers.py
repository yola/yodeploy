import errno
import os
import subprocess
import shutil
import sys

from os.path import join

from nose.plugins.skip import SkipTest

from yodeploy.deploy import deploy
from yodeploy.tests import deployconf
from yodeploy.application import Application

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


def mock_using_current_venv(*args):
    """Return the directory that houses the python bin."""
    if not hasattr(sys, 'real_prefix'):
        raise SkipTest
    return join(os.path.dirname(sys.executable), '..')


def patch_deploy_venv(patch_with=None):
    """Patch the Application virtual env deploy.

    Tests do not have pre-built envs to download. Tell Application to use
    the same env being used to run the tests.
    """
    original_fun = Application.deploy_ve
    patch_with = patch_with or mock_using_current_venv
    Application.deploy_ve = patch_with
    return original_fun


def build_sample(app_name, version='1'):
    """Call build_artifact in the sample app."""
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
    if err or p.wait() != 0:
        raise Exception(out + err)


def deploy_sample(app_name, version="1"):
    """Deploy the sample app to tests/filesys/deployed/app_name/."""
    orig_deploy_ve_fun = patch_deploy_venv()
    args = {
        'app': app_name,
        'target': 'master',
        'config': deployconf_fn,
        'version': version,
        'deploy_settings': deployconf.deploy_settings
    }
    deploy(**args)
    patch_deploy_venv(orig_deploy_ve_fun)
