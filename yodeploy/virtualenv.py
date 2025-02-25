

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


def get_python_version(compat, is_deploy=False):
    """Return Python version for VE based on context.

    Args:
        compat: Compat level from deploy/compat (always present).
        is_deploy: True if building deploy VE, forces Python 3.
    """
    # Deploy VE always Python 3
    if is_deploy:
        python3 = shutil.which('python3')
        if not python3:
            log.error('python3 not found in PATH for deploy VE')
            sys.exit(1)
        return subprocess.check_output(
            [python3, '-c',
             'import sys; print(".".join(map(str, sys.version_info[:2])))']
        ).decode().strip()

    # App VE uses compat directly
    if compat == 4:
        return '2.7'
    # Default to system Python 3 for compat 5 or other values
    python3 = shutil.which('python3')
    if not python3:
        log.error('python3 not found in PATH')
        sys.exit(1)
    return subprocess.check_output(
        [python3, '-c',
         'import sys; print(".".join(map(str, sys.version_info[:2])))']
    ).decode().strip()


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
    req_file = os.path.join(os.path.abspath(app_dir), req_file)

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
                python_path, '-m', 'virtualenv', ve_dir,
                '--no-download'])
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
    except subprocess.CalledProcessError as e:
        log.error('Failed to create VE: %s', e)
        log.error('Stdout: %s', e.stdout.decode())
        log.error('Stderr: %s', e.stderr.decode())
        sys.exit(1)

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
    log.debug('Making virtualenv relocatable')

    # Python 3 venv is inherently relocatable
    if python_version.startswith('3.'):
        return

    # For Python 2, reset app data to ensure relocatability
    if python_version == '2.7':
        subprocess.check_call([
            sys.executable, '-m', 'virtualenv', ve_dir, '--reset-app-data'])
        fix_local_symlinks(ve_dir)
        remove_fragile_symlinks(ve_dir)

    # Make activate relocatable, using approach taken in
    # https://github.com/pypa/virtualenv/pull/236
    activate = []
    activate_path = os.path.join(ve_dir, 'bin', 'activate')
    if not os.path.exists(activate_path):
        log.error('activate script missing in %s', ve_dir)
        return
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
    with open(activate_path, 'w') as f:
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


VERSION = "{}.{}".format(*sys.version_info)
PY_VERSION = "python{}.{}".format(*sys.version_info)
ABI_FLAGS = getattr(sys, "abiflags", "")
OK_ABS_SCRIPTS = [
    "python",
    PY_VERSION,
    "activate",
    "activate.bat",
    "activate_this.py",
    "activate.fish",
    "activate.csh",
    "activate.xsh",
]


def make_environment_relocatable(home_dir):
    """
    Makes the already-existing environment use relative paths, and takes out
    the #!-based environment selection in scripts.
    """
    home_dir, lib_dir, inc_dir, bin_dir = path_locations(home_dir)
    activate_this = os.path.join(bin_dir, "activate_this.py")
    if not os.path.exists(activate_this):
        log.critical(
            "The environment doesn't have a file %s -- please re-run virtualenv " "on this environment to update it",
            activate_this,
        )
    fixup_scripts(home_dir, bin_dir)
    fixup_pth_and_egg_link(home_dir)


def fixup_pth_and_egg_link(home_dir, sys_path=None):
    """Makes .pth and .egg-link files use relative paths"""
    home_dir = os.path.normcase(os.path.abspath(home_dir))
    if sys_path is None:
        sys_path = sys.path
    for a_path in sys_path:
        if not a_path:
            a_path = "."
        if not os.path.isdir(a_path):
            continue
        a_path = os.path.normcase(os.path.abspath(a_path))
        if not a_path.startswith(home_dir):
            log.debug("Skipping system (non-environment) directory %s", a_path)
            continue
        for filename in os.listdir(a_path):
            filename = os.path.join(a_path, filename)
            if filename.endswith(".pth"):
                if not os.access(filename, os.W_OK):
                    log.warning("Cannot write .pth file %s, skipping", filename)
                else:
                    fixup_pth_file(filename)
            if filename.endswith(".egg-link"):
                if not os.access(filename, os.W_OK):
                    log.warning("Cannot write .egg-link file %s, skipping", filename)
                else:
                    fixup_egg_link(filename)


def fixup_scripts(_, bin_dir):
    new_shebang_args = ("/usr/bin/env", VERSION, "")

    # This is what we expect at the top of scripts:
    shebang = "#!{}".format(
        os.path.normcase(os.path.join(os.path.abspath(bin_dir), "python{}".format(new_shebang_args[2])))
    )
    # This is what we'll put:
    new_shebang = "#!{} python{}{}".format(*new_shebang_args)

    for filename in os.listdir(bin_dir):
        filename = os.path.join(bin_dir, filename)
        if not os.path.isfile(filename):
            # ignore child directories, e.g. .svn ones.
            continue
        with open(filename, "rb") as f:
            try:
                lines = f.read().decode("utf-8").splitlines()
            except UnicodeDecodeError:
                # This is probably a binary program instead
                # of a script, so just ignore it.
                continue
        if not lines:
            log.warning("Script %s is an empty file", filename)
            continue

        old_shebang = lines[0].strip()
        old_shebang = old_shebang[0:2] + os.path.normcase(old_shebang[2:])

        if not old_shebang.startswith(shebang):
            if os.path.basename(filename) in OK_ABS_SCRIPTS:
                log.debug("Cannot make script %s relative", filename)
            elif lines[0].strip() == new_shebang:
                log.info("Script %s has already been made relative", filename)
            else:
                log.warning(
                    "Script %s cannot be made relative (it's not a normal script that starts with %s)",
                    filename,
                    shebang,
                )
            continue
        log.warning("Making script %s relative", filename)
        script = relative_script([new_shebang] + lines[1:])
        with open(filename, "wb") as f:
            f.write("\n".join(script).encode("utf-8"))


def fixup_egg_link(filename):
    with open(filename) as f:
        link = f.readline().strip()
    if os.path.abspath(link) != link:
        log.debug("Link in %s already relative", filename)
        return
    new_link = make_relative_path(filename, link)
    log.warning("Rewriting link {} in {} as {}".format(link, filename, new_link))
    with open(filename, "w") as f:
        f.write(new_link)


def make_relative_path(source, dest, dest_is_directory=True):
    """
    Make a filename relative, where the filename is dest, and it is
    being referred to from the filename source.

        >>> make_relative_path('/usr/share/something/a-file.pth',
        ...                    '/usr/share/another-place/src/Directory')
        '../another-place/src/Directory'
        >>> make_relative_path('/usr/share/something/a-file.pth',
        ...                    '/home/user/src/Directory')
        '../../../home/user/src/Directory'
        >>> make_relative_path('/usr/share/a-file.pth', '/usr/share/')
        './'
    """
    source = os.path.dirname(source)
    if not dest_is_directory:
        dest_filename = os.path.basename(dest)
        dest = os.path.dirname(dest)
    else:
        dest_filename = None
    dest = os.path.normpath(os.path.abspath(dest))
    source = os.path.normpath(os.path.abspath(source))
    dest_parts = dest.strip(os.path.sep).split(os.path.sep)
    source_parts = source.strip(os.path.sep).split(os.path.sep)
    while dest_parts and source_parts and dest_parts[0] == source_parts[0]:
        dest_parts.pop(0)
        source_parts.pop(0)
    full_parts = [".."] * len(source_parts) + dest_parts
    if not dest_is_directory and dest_filename is not None:
        full_parts.append(dest_filename)
    if not full_parts:
        # Special case for the current directory (otherwise it'd be '')
        return "./"
    return os.path.sep.join(full_parts)


def fixup_pth_file(filename):
    lines = []
    with open(filename) as f:
        prev_lines = f.readlines()
    for line in prev_lines:
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("import ") or os.path.abspath(line) != line:
            lines.append(line)
        else:
            new_value = make_relative_path(filename, line)
            if line != new_value:
                log.debug("Rewriting path {} as {} (in {})".format(line, new_value, filename))
            lines.append(new_value)
    if lines == prev_lines:
        log.info("No changes to .pth file %s", filename)
        return
    log.warning("Making paths in .pth file %s relative", filename)
    with open(filename, "w") as f:
        f.write("\n".join(lines) + "\n")


FILE_PATH = __file__ if os.path.isabs(__file__) else os.path.join(os.getcwd(), __file__)


def relative_script(lines):
    """Return a script that'll work in a relocatable environment."""
    activate = (
        "import os; "
        "activate_this=os.path.join(os.path.dirname(os.path.realpath(__file__)), 'activate_this.py'); "
        "exec(compile(open(activate_this).read(), activate_this, 'exec'), { '__file__': activate_this}); "
        "del os, activate_this"
    )
    # Find the last future statement in the script. If we insert the activation
    # line before a future statement, Python will raise a SyntaxError.
    activate_at = None
    for idx, line in reversed(list(enumerate(lines))):
        if line.split()[:3] == ["from", "__future__", "import"]:
            activate_at = idx + 1
            break
    if activate_at is None:
        # Activate after the shebang.
        activate_at = 1
    return lines[:activate_at] + ["", activate, ""] + lines[activate_at:]


def path_locations(home_dir, dry_run=False):
    """Return the path locations for the environment (where libraries are,
    where scripts go, etc)"""
    home_dir = os.path.abspath(home_dir)
    lib_dir, inc_dir, bin_dir = None, None, None
    lib_dir = join(home_dir, "lib", PY_VERSION)
    inc_dir = join(home_dir, "include", PY_VERSION + ABI_FLAGS)
    bin_dir = join(home_dir, "bin")
    return home_dir, lib_dir, inc_dir, bin_dir


def join(*chunks):
    line = "".join(chunks)
    sep = ("\\" in line and "\\") or ("/" in line and "/") or "/"
    return sep.join(chunks)
