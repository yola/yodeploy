from __future__ import absolute_import

import argparse
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

import yola.deploy.config
import yola.deploy.repository
import yola.deploy.util

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


def create_ve(app_dir, pypi=None):
    log.info('Building virtualenv')
    ve_dir = os.path.join(app_dir, 'virtualenv')

    if pypi is None:
        pypi = []
    else:
        pypi = ['--index-url', pypi]

    # Monkey patch a logger into virtualenv, usually created in main()
    # Newer virtualenvs won't need this
    if not hasattr(virtualenv, 'logger'):
        virtualenv.logger = virtualenv.Logger([
            (virtualenv.Logger.level_for_integer(2), sys.stdout)])

    virtualenv.create_environment(ve_dir, site_packages=False,
                                  use_distribute=True)
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

    # Update to distribute 0.6.13 for
    # https://bitbucket.org/tarek/distribute/issue/163
    cmd = [os.path.join(ve_dir, 'bin', 'python'),
           os.path.join(ve_dir, 'bin', 'easy_install'),
          ] + pypi + [
           'distribute==0.6.13']
    subprocess.check_call(cmd)

    if requirements:
        cmd = [os.path.join(ve_dir, 'bin', 'python'),
               os.path.join(ve_dir, 'bin', 'easy_install'),
              ] + pypi
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


def main(deploy_settings_fn='/opt/deploy/config/deploy.py'):
    parser = argparse.ArgumentParser(
            description="Prepares virtualenv bundles. "
                        "If a virtualenv with the right hash already exists "
                        "in the store, it'll be downloaded and extracted, "
                        "unless --force is specified.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', metavar='FILE',
                        default=deploy_settings_fn,
                        help='Location of the Deploy configuration file.')
    parser.add_argument('-a', '--app', metavar='NAME',
                        help='Application name')
    parser.add_argument('--target', metavar='TARGET',
                        default='master',
                        help='Target to store/retrieve virtualenvs from')
    parser.add_argument('--env', dest='target', help=argparse.SUPPRESS)
    parser.add_argument('--hash',
                        action='store_true',
                        help="Only determine the virtualenv's version")
    parser.add_argument('-u', '--upload',
                        action='store_true',
                        help="Upload the resultant virtualenv to the "
                             "repository, if there isn't one of this version "
                             "there already")
    parser.add_argument('-d', '--download',
                        action='store_true',
                        help='Download a pre-built ve from the repository')
    parser.add_argument('-f', '--force',
                        action='store_true',
                        help='Overwrite the existing virtualenv')
    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help='Increase verbosity')

    options = parser.parse_args()
    if not os.path.isfile('requirements.txt'):
        parser.error('requirements.txt does not exist')

    if not options.hash and (options.download or options.upload):
        if not options.app:
            parser.error('Application name must be specified')

    if options.verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    deploy_settings = yola.deploy.config.load_settings(options.config)
    repository = yola.deploy.repository.get_repository(deploy_settings)

    version = ve_version(sha224sum('requirements.txt'))
    if options.hash:
        print version
        return

    existing_ve = os.path.exists('virtualenv')
    if os.path.exists('virtualenv/.hash'):
        with open('virtualenv/.hash', 'r') as f:
            existing_ve = f.read().strip()

    if existing_ve:
        if existing_ve == version and not options.force:
            log.info('Existing virtualenv matches requirements.txt')
            options.download = False
        else:
            shutil.rmtree('virtualenv')

    if options.download:
        downloaded = False
        try:
            download_ve(repository, options.app, version, options.target)
            downloaded = True
        except KeyError:
            log.warn('No existing virtualenv, building...')
        if downloaded:
            options.upload = False
            yola.deploy.util.extract_tar('virtualenv.tar.gz', 'virtualenv')

    if not os.path.isdir('virtualenv'):
        create_ve('.', pypi=deploy_settings.get('pypi'))

    if options.upload:
        upload_ve(repository, options.app, version, options.target,
                  overwrite=options.force)

if __name__ == '__main__':
    main()
