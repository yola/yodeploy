import errno
import os
import subprocess
import shutil
import sys
import unittest

from os.path import join


from yodeploy.application import Application
from yodeploy.deploy import deploy
from yodeploy.test_integration import deployconf
from yodeploy.util import ignoring

tests_dir = os.path.dirname(__file__)
bin_dir = os.path.join(tests_dir, '..', 'cmds')
deployconf_fn = deployconf.__file__.rstrip('c')


def rmdir(path):
    with ignoring(errno.ENOENT):
        shutil.rmtree(path)


def rm(path):
    with ignoring(errno.ENOENT):
        os.remove(path)


def clear(app_name):
    store = deployconf.deploy_settings.artifacts.store_settings.local.directory
    rmdir(join(store, app_name))
    rmdir(join(deployconf.deploy_settings.paths.apps, app_name))


def cleanup_venv(app_name):
    app_dir = os.path.join(tests_dir, 'samples', app_name)
    rmdir(join(tests_dir, 'filesys', 'artifacts', app_name))
    rmdir(join(app_dir, 'virtualenv'))
    rm(join(app_dir, 'virtualenv.tar.gz'))


def mock_using_current_venv(*args):
    """Return the directory that houses the python bin."""
    py2ve = not getattr(sys, 'real_prefix', None)  # python 2.7
    py3ve = getattr(sys, 'base_prefix', None) != sys.prefix  # py >3.3

    if not py2ve and not py3ve:
        raise unittest.SkipTest("Test requires a virtual environment.")

    return os.path.realpath(join(os.path.dirname(sys.executable), '..'))


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
    """Clear all prev builds and call build_artifact in the sample app."""
    clear(app_name)
    script_path = os.path.join(bin_dir, 'build_artifact.py')
    app_dir = os.path.join(tests_dir, 'samples', app_name)
    env = {
        'PATH': os.environ['PATH'],
        'BUILD_NUMBER': version,
        'GIT_BRANCH': 'master',
        'YOLA_SRC': os.path.join(tests_dir, 'samples')
    }

    p = subprocess.Popen(
        (sys.executable, script_path, '--no-virtualenvs',
            '--config', deployconf_fn),
        cwd=app_dir,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env)
    out, err = p.communicate()

    if p.wait() != 0:
        raise Exception(out + err)


def deploy_sample(app_name, version="1"):
    """Deploy the sample app to test_integration/filesys/deployed/app_name/."""
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
