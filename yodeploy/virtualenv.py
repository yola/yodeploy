from __future__ import absolute_import

import hashlib
import logging
import os
import subprocess
import sys
import shutil
import tarfile

try:
    import sysconfig
    hush_pyflakes = sysconfig
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


def download_ve(repository, app, ve_version, target='master',
                dest='virtualenv.tar.gz'):
    artifact = 'virtualenv-%s.tar.gz' % ve_version
    with repository.get(app, target=target, artifact=artifact) as f1:
        with open(dest, 'w') as f2:
            shutil.copyfileobj(f1, f2)


def upload_ve(repository, app, ve_version, target='master',
              source='virtualenv.tar.gz', overwrite=False):
    log.debug('Uploading virtualenv %s for %s', ve_version, app)
    artifact = 'virtualenv-%s.tar.gz' % ve_version
    versions = repository.list_versions(app, target, artifact)
    version = '1'
    if versions:
        if not overwrite:
            log.error('Skipping: already exists')
            return
        version = str(int(versions[-1]) + 1)
    with open(source) as f:
        repository.put(app, version, f, {}, target, artifact)


def create_ve(app_dir, pypi=None, req_file='requirements.txt'):
    log.info('Building virtualenv')
    ve_dir = os.path.join(app_dir, 'virtualenv')

    if pypi is None:
        pypi = []
    else:
        pypi = ['--extra-index-url', pypi]

    # Monkey patch a logger into virtualenv, usually created in main()
    # Newer virtualenvs won't need this
    if not hasattr(virtualenv, 'logger'):
        virtualenv.logger = virtualenv.Logger([
            (virtualenv.Logger.level_for_integer(2), sys.stdout)])

    virtualenv.create_environment(ve_dir, site_packages=False)
    with open(os.path.join(app_dir, req_file), 'r') as f:
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
        cmd = [os.path.join('bin', 'python'),
               os.path.join('bin', 'pip'), 'install', 'wheel'
              ] + pypi
        subprocess.check_call(cmd, cwd=ve_dir)
        cmd = [os.path.join('bin', 'python'),
               os.path.join('bin', 'pip'), 'wheel',
              ] + pypi
        cmd += requirements
        subprocess.check_call(cmd, cwd=ve_dir)
        cmd = [os.path.join('bin', 'python'),
               os.path.join('bin', 'pip'), 'install', '--no-index'
              ] + pypi
        cmd += requirements
        subprocess.check_call(cmd, cwd=ve_dir)

    relocateable_ve(ve_dir)
    with open(os.path.join(ve_dir, '.hash'), 'w') as f:
        f.write(ve_version(sha224sum(os.path.join(app_dir, req_file))))

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
