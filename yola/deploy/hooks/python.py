import hashlib
import logging
import os
import shutil
import subprocess
import sys
import tarfile

try:
    import sysconfig
except ImportError:
    class sysconfig:
        @classmethod
        def get_python_version(cls):
            return '%i.%i' % sys.version_info[:2]

        @classmethod
        def get_platform(cls):
            import distutils.util
            return distutils.util.get_platform()

import virtualenv

from .base import DeployHook

# TODO: Get this from configuration
YOLAPI_URL = 'https://yolapi.yola.net/simple/'

log = logging.getLogger(__name__)


def sha224sum(filename):
    m = hashlib.sha224()
    with open(filename) as f:
        m.update(f.read())
    return m.hexdigest()


def ve_version(req_hash):
    return '%s-%s-%s' % (sysconfig.get_python_version(),
                         sysconfig.get_platform(),
                         req_hash)


def download_ve(app, version, artifacts_factory, dest='virtualenv.tar.gz'):
    artifacts = artifacts_factory('virtualenv-%s.tar.gz' % version)
    artifacts.update_versions()
    if artifacts.versions.latest:
        log.debug('Downloading existing virtualenv %s for %s', version, app)
        artifacts.download(dest)
        return True
    else:
        log.debug('No existing virtualenv %s for %s', version, app)
        return False


def upload_ve(app, version, artifacts_factory, filename):
    log.debug('Uploading virtualenv %s for %s', version, app)
    artifacts = artifacts_factory('virtualenv-%s.tar.gz' % version)
    artifacts.update_versions()
    artifacts.upload(filename)


def unpack_ve(tarball='virtualenv.tar.gz', directory='.'):
    log.debug('Unpacking virtualenv.tar.gz')
    t = tarfile.open(tarball, 'r')
    try:
        t.extractall(directory)
    finally:
        t.close()


def create_ve(app_dir):
    log.info('Building virtualenv')
    ve_dir = os.path.join(app_dir, 'virtualenv')
    # Monkey patch a logger into virtualenv, usually created in main()
    # Newer virtualenvs won't need this
    if not hasattr(virtualenv, 'logger'):
        virtualenv.logger = virtualenv.Logger([
            (virtualenv.Logger.level_for_integer(2), sys.stdout)])

    virtualenv.create_environment(ve_dir, site_packages=False)
    with open(os.path.join(app_dir, 'requirements.txt'), 'r') as f:
        requirements = []
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith('-'):
                continue
            if line.startswith('#'):
                continue
            requirements.append(line)

    if requirements:
        cmd = [os.path.join(ve_dir, 'bin', 'python'),
               os.path.join(ve_dir, 'bin', 'easy_install'),
               '--index-url', YOLAPI_URL]
        cmd += requirements
        subprocess.check_call(cmd)

    relocateable_ve(ve_dir)
    with open(os.path.join(ve_dir, '.hash'), 'w') as f:
        f.write(ve_version(sha224sum(os.path.join(app_dir,
                                                  'requirements.txt'))))

    cwd = os.getcwd()
    os.chdir(app_dir)
    t = tarfile.open('virtualenv.tar.gz', 'w:gz')
    try:
        t.add('virtualenv')
    finally:
        t.close()
        os.chdir(cwd)


def relocateable_ve(ve_dir):
    log.debug('Making virtualenv relocatable')
    virtualenv.make_environment_relocatable(ve_dir)

    # Make activate relocatable, using approach taken in
    # https://github.com/pypa/virtualenv/pull/236
    activate = []
    with open(os.path.join(ve_dir, 'bin', 'activate')) as f:
        for line in f:
            line = line.strip()
            if line == 'deactivate () {':
                activate += ['ACTIVATE_PATH_FALLBACK="$_"', '']
            if line.startswith('VIRTUAL_ENV='):
                activate += [
                    '# attempt to determine VIRTUAL_ENV in relocatable way',
                    'if [ ! -z "${BASH_SOURCE:-}" ]; then',
                    '    # bash',
                    '    ACTIVATE_PATH="${BASH_SOURCE}"',
                    'elif [ ! -z "${DASH_SOURCE:-}" ]; then',
                    '    # dash',
                    '    ACTIVATE_PATH="${DASH_SOURCE}"',
                    'elif [ ! -z "${ZSH_VERSION:-}" ]; then',
                    '    # zsh',
                    '    ACTIVATE_PATH="$0"',
                    'elif [ ! -z "${KSH_VERSION:-}" ] '
                         '|| [ ! -z "${.sh.version:}" ]; then',
                    '    # ksh - we have to use history, '
                                'and unescape spaces before quoting',
                    '    ACTIVATE_PATH="$(history -r -l -n | head -1 | sed -e '
                        '\'s/^[\\t ]*\\(\\.\\|source\\) *//;s/\\\\ / /g\')"',
                    'elif [ "$(basename "$ACTIVATE_PATH_FALLBACK")" == '
                           '"activate.sh" ]; then',
                    '    ACTIVATE_PATH="${ACTIVATE_PATH_FALLBACK}"',
                    'else',
                    '    ACTIVATE_PATH=""',
                    'fi',
                    '',
                    '# default to non-relocatable path',
                ]
            if line == 'export VIRTUAL_ENV':
                activate += [
                    'if [ ! -z "${ACTIVATE_PATH:-}" ]; then',
                    '    VIRTUAL_ENV="$(cd '
                        '"$(dirname "${ACTIVATE_PATH}")/.."; pwd)"',
                    'fi',
                    'unset ACTIVATE_PATH',
                    'unset ACTIVATE_PATH_FALLBACK',
                ]
            activate.append(line)
    with open(os.path.join(ve_dir, 'bin', 'activate'), 'w') as f:
        f.write('\n'.join(activate))


class PythonApp(DeployHook):
    def prepare(self):
        app_dir = os.path.join(self.root, 'versions', self.version)
        requirements = os.path.join(app_dir, 'requirements.txt')
        if os.path.exists(requirements):
            self.deploy_ve()
        super(PythonApp, self).prepare()

    def deploy_ve(self):
        log = logging.getLogger(__name__)
        app_dir = os.path.join(self.root, 'versions', self.version)
        ve_hash = ve_version(sha224sum(
                os.path.join(app_dir, 'requirements.txt')))
        ve_working = os.path.join(self.root, 'virtualenvs', 'unpack')
        ve_dir = os.path.join(self.root, 'virtualenvs', ve_hash)
        tarball = os.path.join(ve_working, 'virtualenv.tar.gz')

        log.debug('Deploying virtualenv %s', ve_hash)

        if not os.path.exists(ve_working):
            os.makedirs(ve_working)
        download_ve(self.app, ve_hash, self.artifacts_factory, tarball)
        unpack_ve(tarball, ve_working)
        if os.path.exists(ve_dir):
            shutil.rmtree(ve_dir)
        os.rename(os.path.join(ve_working, 'virtualenv'), ve_dir)
        os.symlink(os.path.join('..', '..', 'virtualenvs', ve_hash),
                   os.path.join(app_dir, 'virtualenv'))
