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

import yola.deploy.artifacts
import yola.deploy.config
import yola.deploy.util

log = logging.getLogger(__name__)
# TODO: Get this from configuration
YOLAPI_URL = 'https://yolapi.yola.net/simple/'


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
    artifacts = artifacts_factory(filename='virtualenv-%s.tar.gz' % version,
                                  app=app)
    artifacts.update_versions()
    if artifacts.versions.latest:
        log.debug('Downloading existing virtualenv %s for %s', version, app)
        artifacts.download(dest)
    else:
        raise KeyError('No existing virtualenv %s for %s' % (version, app))


def upload_ve(app, version, artifacts_factory, filename, overwrite=False):
    log.debug('Uploading virtualenv %s for %s', version, app)
    artifacts = artifacts_factory(filename='virtualenv-%s.tar.gz' % version,
                                  app=app)
    artifacts.update_versions()
    if overwrite or artifacts.versions.latest is None:
        artifacts.upload(filename)


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

    # Update to distribute 0.6.13 for
    # https://bitbucket.org/tarek/distribute/issue/163
    cmd = [os.path.join(ve_dir, 'bin', 'python'),
           os.path.join(ve_dir, 'bin', 'easy_install'),
           '--index-url', YOLAPI_URL, 'distribute==0.6.13']
    subprocess.check_call(cmd)

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


def main():
    parser = argparse.ArgumentParser(
            description="Prepares virtualenv bundles. "
                        "If a virtualenv with the right hash already exists "
                        "in the store, it'll be downloaded and extracted, "
                        "unless --force is specified.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', metavar='FILE',
                        default='/opt/deploy/config/deploy.py',
                        help='Location of the Deploy configuration file.')
    parser.add_argument('-a', '--app', metavar='NAME',
                        help='Application name')
    parser.add_argument('--target', metavar='TARGET',
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

    if options.download or options.upload:
        deploy_settings = yola.deploy.config.load_settings(options.config)
        artifacts_factory = yola.deploy.artifacts.build_artifacts_factory(
                options.app, options.target, deploy_settings)

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
            options.download = False
        else:
            shutil.rmtree('virtualenv')

    if options.download:
        downloaded = False
        try:
            download_ve(options.app, version, artifacts_factory)
            downloaded = True
        except KeyError:
            pass
        if downloaded:
            options.upload = False
            yola.deploy.util.extract_tar('virtualenv.tar.gz', 'virtualenv')

    if not os.path.isdir('virtualenv'):
        create_ve('.')

    if options.upload:
        upload_ve(options.app, version, artifacts_factory, 'virtualenv.tar.gz',
                  options.force)

if __name__ == '__main__':
    main()
