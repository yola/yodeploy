from __future__ import absolute_import

import hashlib
import logging
import os
import subprocess
import sys
import shutil
import sysconfig
import tarfile

from pkg_resources import parse_version
import virtualenv

log = logging.getLogger(__name__)


def sha224sum(filename):
    m = hashlib.sha224()
    with open(filename, 'rb') as f:
        m.update(f.read())
    return m.hexdigest()


def get_python_version(compat):
    """Return the version of Python that an app will use.

    Based on the compat level.
    """
    if compat < 5:
        return '2.7'
    if sys.version_info.major == 3:
        return sysconfig.get_python_version()
    return subprocess.check_output((
        'python3', '-c',
        'import sysconfig; print(sysconfig.get_python_version())'
    )).strip()


def get_id(filename, python_version, platform):
    """Calculate the ID of a virtualenv for the given requirements.txt"""
    req_hash = sha224sum(filename)
    return '%s-%s-%s' % (python_version, platform, req_hash)


def download_ve(repository, app, virtualenv_id, target='master',
                dest='virtualenv.tar.gz'):
    artifact = 'virtualenv-%s.tar.gz' % virtualenv_id
    with repository.get(app, target=target, artifact=artifact) as f1:
        with open(dest, 'wb') as f2:
            shutil.copyfileobj(f1, f2)


def upload_ve(repository, app, virtualenv_id, target='master',
              source='virtualenv.tar.gz', overwrite=False):
    log.debug('Uploading virtualenv %s for %s', virtualenv_id, app)
    artifact = 'virtualenv-%s.tar.gz' % virtualenv_id
    versions = repository.list_versions(app, target, artifact)
    version = '1'
    if versions:
        if not overwrite:
            log.error('Skipping: already exists')
            return
        version = str(int(versions[-1]) + 1)
    with open(source, 'rb') as f:
        repository.put(app, version, f, {}, target, artifact)


def create_ve(
        app_dir, python_version, platform, pypi=None,
        req_file='requirements.txt',
        verify_req_install=True):
    log.info('Building virtualenv')
    ve_dir = os.path.join(app_dir, 'virtualenv')
    ve_python = os.path.join(ve_dir, 'bin', 'python')
    req_file = os.path.join(os.path.abspath(app_dir), req_file)

    # The venv module makes a lot of our reclocateability problems go away, so
    # we only use the virtualenv library on Python 2.
    if python_version.startswith('3.'):
        subprocess.check_call((
            'python%s' % python_version, '-m', 'venv', ve_dir))
        pip_version = subprocess.check_output((
            ve_python, '-c', 'import ensurepip; print(ensurepip.version())'))
        if parse_version(pip_version) < parse_version('9'):
            pip_install(ve_dir, pypi, '-U', 'pip')
        pip_install(ve_dir, pypi, 'wheel')
    elif python_version == sysconfig.get_python_version():
        virtualenv.create_environment(ve_dir, site_packages=False)
    else:
        subprocess.check_call((
            sys.executable, virtualenv.__file__.rstrip('c'),
            '-p', 'python%s' % python_version,
            '--no-site-packages', ve_dir))

    pip_install(ve_dir, pypi, '-U', 'setuptools')

    log.info('Installing requirements')
    pip_install(ve_dir, pypi, '-r', req_file)

    if verify_req_install:
        log.info('Verifying requirements were met')
        check_requirements(ve_dir)

    relocateable_ve(ve_dir, python_version)

    ve_id = get_id(os.path.join(app_dir, req_file), python_version, platform)
    with open(os.path.join(ve_dir, '.hash'), 'w') as f:
        f.write(ve_id)
        f.write('\n')

    log.info('Building virtualenv tarball')
    cwd = os.getcwd()
    os.chdir(app_dir)
    t = tarfile.open('virtualenv.tar.gz', 'w:gz')
    try:
        t.add('virtualenv')
    finally:
        t.close()
        os.chdir(cwd)


def pip_install(ve_dir, pypi, *arguments):
    sub_log = logging.getLogger(__name__ + '.pip')

    cmd = [os.path.join('bin', 'python'), '-m', 'pip', 'install']
    if pypi:
        cmd += ['--index-url', pypi]
    cmd += arguments

    p = subprocess.Popen(cmd, cwd=ve_dir, stdout=subprocess.PIPE)
    for line in iter(p.stdout.readline, b''):
        line = line.decode('utf-8').strip()
        sub_log.info('%s', line)

    if p.wait() != 0:
        log.error('pip exited non-zero (%i)', p.returncode)
        sys.exit(1)


def check_requirements(ve_dir):
    """Run pip check"""
    p = subprocess.Popen(
        (os.path.join(ve_dir, 'bin', 'python'), '-m', 'pip', 'check'),
        stdout=subprocess.PIPE)
    out, _ = p.communicate()

    if p.returncode == 0:
        log.info(out)
    else:
        log.error(out or 'Requirements check failed for unknown reasons')
        sys.exit(1)


def relocateable_ve(ve_dir, python_version):
    # We can only call into the virtualenv module for operating on a
    # Python 2 virtualenv, in Python 2.
    if sys.version_info.major == 3 and python_version == '2.7':
        cmd = [
            os.path.join(ve_dir, 'bin', 'python'), '-c',
            'import sys; sys.path.append("%(ve_path)s"); '
            'sys.path.append("%(my_path)s"); '
            'from yodeploy import virtualenv; '
            'virtualenv.relocateable_ve("%(ve_dir)s", "%(python_version)s")'
            % {
                've_path': os.path.dirname(virtualenv.__file__),
                'my_path': os.path.join(os.path.dirname(__file__), '..'),
                've_dir': ve_dir,
                'python_version': python_version,
            }]
        subprocess.check_call(cmd)
        return

    log.debug('Making virtualenv relocatable')

    # Python 3 venv virtualenvs don't have these problems
    if python_version == '2.7':
        virtualenv.make_environment_relocatable(ve_dir)
        fix_local_symlinks(ve_dir)
        remove_fragile_symlinks(ve_dir)

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


def fix_local_symlinks(ve_dir):
    """Make symlinks in the local dir relative.

    The symlinks in the local dir should just point (relatively) at the
    equivalent directories outside the local tree, for relocateability.
    """
    local = os.path.join(ve_dir, 'local')
    if not os.path.exists(local):
        return
    for fn in os.listdir(local):
        symlink = os.path.join(local, fn)
        target = os.path.join('..', fn)
        os.unlink(symlink)
        os.symlink(target, symlink)


def remove_fragile_symlinks(ve_dir):
    """Remove symlinks to parent virtualenv.

    When we create a virtualenv with a Python from another virtualenv, we don't
    want to leave symlinks pointing back to the virtualenv we used.  In a
    production environment, it probably won't be there.
    """
    if getattr(sys, 'real_prefix', sys.prefix) == sys.prefix:
        return
    ve_prefix = sys.prefix
    home_dir, lib_dir, inc_dir, bin_dir = virtualenv.path_locations(ve_dir)
    for fn in os.listdir(lib_dir):
        path = os.path.join(lib_dir, fn)
        if not os.path.islink(path):
            continue

        dest = os.readlink(path)
        if not dest.startswith(ve_prefix):
            continue

        log.debug('Removing fragile symlink %s -> %s', path, dest)
        os.unlink(path)
