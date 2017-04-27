from __future__ import absolute_import

import hashlib
import logging
import os
import subprocess
import sys
import shutil
import sysconfig
import tarfile

import virtualenv

log = logging.getLogger(__name__)


def sha224sum(filename):
    m = hashlib.sha224()
    with open(filename, 'rb') as f:
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
        with open(dest, 'wb') as f2:
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
    with open(source, 'rb') as f:
        repository.put(app, version, f, {}, target, artifact)


def create_ve(
        app_dir, pypi=None, req_file='requirements.txt',
        verify_req_install=True):
    log.info('Building virtualenv')
    ve_dir = os.path.join(app_dir, 'virtualenv')
    req_file = os.path.join(os.path.abspath(app_dir), req_file)

    virtualenv.create_environment(ve_dir, site_packages=False)
    install_requirements(ve_dir, pypi, req_file)

    if verify_req_install:
        log.info('Verifying requirements were met')
        check_requirements(ve_dir, req_file)

    relocateable_ve(ve_dir)
    with open(os.path.join(ve_dir, '.hash'), 'w') as f:
        f.write(ve_version(sha224sum(os.path.join(app_dir, req_file))))

    log.info('Building virtualenv tarball')
    cwd = os.getcwd()
    os.chdir(app_dir)
    t = tarfile.open('virtualenv.tar.gz', 'w:gz')
    try:
        t.add('virtualenv')
    finally:
        t.close()
        os.chdir(cwd)


def install_requirements(ve_dir, pypi, req_file):
    sub_log = logging.getLogger(__name__ + '.pip')

    log.info('Installing requirements')

    cmd = [
        os.path.join('bin', 'python'), '-m', 'pip', 'install',
        '-r', req_file,
    ]

    if pypi:
        cmd += ['--index-url', pypi]

    p = subprocess.Popen(cmd, cwd=ve_dir, stdout=subprocess.PIPE)
    for line in iter(p.stdout.readline, b''):
        line = line.decode('utf-8').strip()
        sub_log.info('%s', line)
        if line.startswith('Removing'):
            log.error('Requirements were incompatible: %s', line)
            sys.exit(1)

    if p.wait() != 0:
        log.error('pip exited non-zero (%i)', p.returncode)
        sys.exit(1)


def check_requirements(ve_dir, req_file):
    """Given a ve root, and a requriments file, ensure that they are met"""

    with open(req_file, 'r') as f:
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

    script = (
        'import sys, pkg_resources\n'
        'for req in %r:\n'
        '  try:\n'
        '    pkg_resources.get_distribution(req)\n'
        '  except pkg_resources.DistributionNotFound:\n'
        '    pass\n'
        '  except pkg_resources.VersionConflict as e:\n'
        '    print(\n'
        '      "Incompatible requirement: %%s\\n" %% e)\n'
        '    sys.exit(1)\n'
    ) % (requirements,)

    p = subprocess.Popen(
        os.path.join(ve_dir, 'bin', 'python'),
        stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    out, _ = p.communicate(script.encode('utf-8'))

    if p.returncode != 0:
        log.error(out or 'Requirements check failed for unknown reasons')
        sys.exit(1)


def relocateable_ve(ve_dir):
    log.debug('Making virtualenv relocatable')
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
