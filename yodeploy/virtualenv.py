import hashlib
import logging
import os
import subprocess
import sys
import shutil
import tarfile

log = logging.getLogger(__name__)


def sha224sum(filename):
    m = hashlib.sha224()
    with open(filename, 'rb') as f:
        m.update(f.read())
    return m.hexdigest()


def get_python_version(compat, is_deploy=False):
    python3 = shutil.which('python3')
    if not python3:
        log.error(
            'python3 not found in PATH%s' % (
                'for deploy VE' if is_deploy else ''
            )
        )
        sys.exit(1)
    python3_version = subprocess.check_output(
        [
            python3,
            '-c', 'import sys; print(".".join(map(str, sys.version_info[:2])))'
        ]
    ).decode().strip()
    if is_deploy or compat != 4:
        return python3_version
    return '2.7'


def get_id(filename, python_version, platform):
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
        req_file='requirements.txt', verify_req_install=True):
    log.info('Building virtualenv')
    ve_dir = os.path.abspath(os.path.join(app_dir, 'virtualenv'))
    req_file = os.path.join(os.path.abspath(app_dir), req_file)

    if os.path.exists(ve_dir):
        shutil.rmtree(ve_dir)

    python_path = shutil.which('python%s' % python_version)
    if not python_path:
        log.error('Python %s not found in PATH', python_version)
        sys.exit(1)
    log.debug('Using Python path: %s', python_path)

    try:
        if python_version.startswith('3.'):
            log.debug('Creating Python 3 VE with venv: %s', ve_dir)
            subprocess.check_call([python_path, '-m', 'venv', ve_dir])
        else:
            log.debug('Creating Python 2.7 VE with virtualenv: %s', ve_dir)
            subprocess.check_call([
                sys.executable, '-m', 'virtualenv', ve_dir,
                '--python', python_path,
                '--no-download'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        python_bin = os.path.join(ve_dir, 'bin', 'python')
        if not os.path.exists(python_bin):
            log.error('VE created but bin/python missing at %s', python_bin)
            log.debug('VE contents: %s', os.listdir(ve_dir))
            raise FileNotFoundError(f"bin/python not found in {ve_dir}")
        log.debug('VE created, contents: %s', os.listdir(ve_dir))

        pip_install(ve_dir, pypi, '-U', 'pip')
        pip_install(ve_dir, pypi, '-U', 'setuptools')
        pip_install(ve_dir, pypi, 'wheel')
        log.info('Installing requirements')
        pip_install(ve_dir, pypi, '-r', req_file)
        if verify_req_install:
            log.info('Verifying requirements were met')
            check_requirements(ve_dir)
        relocateable_ve(ve_dir, python_version)
        ve_id = get_id(
            os.path.join(app_dir, req_file),
            python_version, platform
        )
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
    except subprocess.CalledProcessError as e:
        log.error('Failed to create VE: %s', e)
        if e.stdout:
            log.error('Stdout: %s', e.stdout.decode())
        if e.stderr:
            log.error('Stderr: %s', e.stderr.decode())
        if os.path.exists(ve_dir):
            shutil.rmtree(ve_dir)
        sys.exit(1)


def pip_install(ve_dir, pypi, *arguments):
    sub_log = logging.getLogger(__name__ + '.pip')
    cmd = [os.path.join(ve_dir, 'bin', 'python'), '-m', 'pip', 'install']
    if pypi:
        cmd += ['--index-url', pypi]
    cmd += arguments
    p = subprocess.Popen(
        cmd, cwd=ve_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = p.communicate()
    for line in stdout.decode().splitlines():
        sub_log.info(line.strip())
    if p.returncode != 0:
        for line in stderr.decode().splitlines():
            sub_log.error(line.strip())
        log.error('pip exited non-zero (%i)', p.returncode)
        sys.exit(1)


def check_requirements(ve_dir):
    p = subprocess.Popen(
        [os.path.join(ve_dir, 'bin', 'python'), '-m', 'pip', 'check'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode == 0:
        log.info(out.decode().strip())
    else:
        log.error(err.decode().strip() or 'Requirements check failed')
        sys.exit(1)


def relocateable_ve(ve_dir, python_version):
    log.debug('Making virtualenv relocatable')
    if python_version.startswith('3.'):
        return
    if python_version == '2.7':
        fix_local_symlinks(ve_dir)
        remove_fragile_symlinks(ve_dir, python_version)
    activate_path = os.path.join(ve_dir, 'bin', 'activate')
    if not os.path.exists(activate_path):
        log.error('activate script missing in %s', ve_dir)
        return
    activate = []
    with open(activate_path) as f:
        for line in f:
            line = line.strip()
            if line == 'deactivate () {':
                activate += ['ACTIVATE_PATH_FALLBACK="$_"', '']
            if line.startswith('VIRTUAL_ENV='):
                activate += [
                    '# attempt to determine VIRTUAL_ENV in relocatable way',
                    'if [ ! -z "${BASH_SOURCE:-}" ]; then',
                    '    ACTIVATE_PATH="${BASH_SOURCE}"',
                    'elif [ ! -z "${DASH_SOURCE:-}" ]; then',
                    '    ACTIVATE_PATH="${DASH_SOURCE}"',
                    'elif [ ! -z "${ZSH_VERSION:-}" ]; then',
                    '    ACTIVATE_PATH="$0"',
                    'elif [ ! -z "${KSH_VERSION:-}" ] '
                         '|| [ ! -z "${.sh.version:}" ]; then',
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
    with open(activate_path, 'w') as f:
        f.write('\n'.join(activate))


def fix_local_symlinks(ve_dir):
    local = os.path.join(ve_dir, 'local')
    if not os.path.exists(local):
        return
    for fn in os.listdir(local):
        symlink = os.path.join(local, fn)
        target = os.path.join('..', fn)
        os.unlink(symlink)
        os.symlink(target, symlink)


def remove_fragile_symlinks(ve_dir, python_version):
    """Remove symlinks to parent virtualenv.
    
    When we create a virtualenv with a Python from another virtualenv, we don't
    want to leave symlinks pointing back to the virtualenv we used.  In a
    production environment, it probably won't be there.
    """
    if getattr(sys, 'real_prefix', sys.prefix) == sys.prefix:
        return
    ve_prefix = sys.prefix
    home_dir = os.path.abspath(ve_dir)
    lib_dir = os.path.join(home_dir, 'lib', 'python' + python_version)
    if not os.path.exists(lib_dir):
        return
    for fn in os.listdir(lib_dir):
        path = os.path.join(lib_dir, fn)
        if not os.path.islink(path):
            continue
        dest = os.readlink(path)
        if not dest.startswith(ve_prefix):
            continue
        log.debug('Removing fragile symlink %s -> %s', path, dest)
        os.unlink(path)
