#!/usr/bin/env python

# Prepares your machine for developing on yodeploy apps
# Will check out:
#  yodeploy:
#    - Installs scripts to ~/bin
#  yoconfigurator:
#    - Installs scripts to ~/bin
#  deployconfigs
#    - Configures configs/hostname.py

import contextlib
import errno
import logging
import netrc
import optparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import urllib2
import urlparse

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import yodeploy.config


GIT_REPO = 'git@github.com:yola/%s.git'
GIT_MIRRORS = (
    ('ctmirror', 'http://git.ct.yola.net/git/yola/%s.git'),
)

log = logging.getLogger('local-bootstrap')


def confirm(message):
    '''Display a Y/n question prompt, and return a boolean'''
    while True:
        print
        input_ = raw_input('%s [Y/n] ' % message)
        input_ = input_.strip().lower()
        if input_ in ('y', 'yes', ''):
            return True
        if input_ in ('n', 'no'):
            return False
        print 'Invalid selection'


def abort(message):
    '''Pretty much what the tin says'''
    log.error(message)
    sys.exit(1)


def binary_available(name):
    '''Check if a program is available in PATH'''
    for dir_ in os.environ.get('PATH', '').split(':'):
        if os.access(os.path.join(dir_, name), os.X_OK):
            return True
    return False


def check_environment():
    '''
    Check that our basic tools exist
    Return YOLA_SRC
    '''
    if not binary_available('git'):
        abort('We require git to be installed')

    bin_ = os.path.expanduser('~/bin')
    bashrc_additions = []
    if not os.path.isdir(bin_):
        if confirm("You don't seem to have a ~/bin directory.\n"
                   "Create it, and add a line to your .bashrc to add it to "
                   "your PATH?"):
            os.mkdir(bin_)
            bashrc_additions.append('export PATH=~/"bin:$PATH"')
            os.environ['PATH'] += ':' + os.path.expanduser('~/bin')

    profiles = [os.path.expanduser(profile) for profile in
                ('~/.bash_profile', '~/.bash_login', '~/.profile')
                if os.path.isfile(os.path.expanduser(profile))]
    profile = None
    if profiles:
        if not confirm("%s exists. Does it source ~/.bashrc?" % profiles[0]):
            profile = profiles[0]
    elif confirm("You don't seem to have a .profile.\n"
                 "Create it, sourcing .bashrc?"):
        profile = os.path.expanduser('~/.profile')
    if profile:
        with open(profile, 'a') as f:
            f.write("# Created by Yola's local-bootstrap\n. ~/.bashrc\n")

    if 'YOLA_SRC' in os.environ:
        yola_src = os.environ['YOLA_SRC']

    if 'YOLA_SRC' in os.environ and os.path.isdir(os.environ['YOLA_SRC']):
        log.info("The YOLA_SRC environment variable exists. Following it")
    else:
        if 'YOLA_SRC' not in os.environ:
            input_ = raw_input('Where do you keep your Yola GIT checkouts? '
                               '[Default: ~/src/]: ')
            input_ = input_.strip()
            if not input_:
                input_ = '~/src'
            yola_src = os.path.expanduser(input_)

            if confirm('We can export this as YOLA_SRC in your .bashrc for '
                    'future.\nAdd a line to .bashrc?'):
                # Basic escaping that'll handle spaces and not much else
                input_ = input_.replace(' ', '" "')
                bashrc_additions.append('export YOLA_SRC=%s' % input_)

        if not os.path.isdir(yola_src):
            if confirm("Your %s directory doesn't exist.\nCreate it?"
                       % yola_src):
                os.mkdir(yola_src)

    if bashrc_additions:
        bashrc_additions = ['', "# Added by Yola's local-bootstrap"
                           ] + bashrc_additions + ['']
        with open(os.path.expanduser('~/.bashrc'), 'a') as f:
            f.write('\n'.join(bashrc_additions))

    return yola_src


def check_call(cmd, *args, **kwargs):
    '''Logging wrapper around subprocess.check_call'''
    log.debug('Calling %s', ' '.join(cmd))
    return subprocess.check_call(cmd, *args, **kwargs)


def call(cmd, *args, **kwargs):
    '''
    Logging wrapper around subprocess.call
    Additionally, it eats ENOENT, and rephrases it as returning 127
    '''
    log.debug('Calling %s', ' '.join(cmd))
    try:
        return subprocess.call(cmd, *args, **kwargs)
    except OSError, e:
        if e.errno == errno.ENOENT:
            return 127
        raise


def git(*cmds, **kwargs):
    '''Call git'''
    ignore_fail = kwargs.pop('ignore_fail', False)
    cmd = ('git',) + cmds
    if ignore_fail:
        call(cmd, **kwargs)
    else:
        check_call(cmd, **kwargs)


def git_mirror_available():
    '''See if any git mirrors are available'''
    try:
        our_netrc = netrc.netrc()
    except IOError:
        our_netrc = None

    for name, url in GIT_MIRRORS:
        parsed = urlparse.urlparse(url)
        if parsed.scheme:
            host = parsed.hostname
            port = parsed.scheme
        else:
            # SSH URL
            host = url.split('@', 1)[1].split(':', 1)[0]
            port = 'ssh'
        try:
            socket.getaddrinfo(host, port)
        except socket.gaierror:
            continue

        if port in ('http', 'https'):
            # We assume http / https requires auth
            # Maybe we should probe and see...
            if our_netrc is None or our_netrc.authenticators(host) is None:
                log.info("A mirror is available (%s), but there are no "
                         "credentials for it in ~/.netrc", url)
                continue

        return name, url


@contextlib.contextmanager
def chdir(directory):
    '''with chdir: ...'''
    pwd = os.getcwd()
    os.chdir(directory)
    try:
        yield
    finally:
        os.chdir(pwd)


def clone(app, yola_src, branch='master'):
    '''Clone a Yola git repository'''
    appdir = os.path.join(yola_src, app)

    if (os.path.isdir(appdir)
            and not os.path.isdir(os.path.join(appdir, '.git'))):
        if confirm("%s exists but isn't a git repository"):
            shutil.rmtree(appdir)

    mirror = git_mirror_available()
    if mirror:
        mirror, mirror_url = mirror

    if not os.path.isdir(appdir):
        git('init', '--quiet', appdir)

    with chdir(appdir):
        git('remote', 'rm', 'origin', ignore_fail=True)
        git('remote', 'add', 'origin', GIT_REPO % app)
        if mirror:
            git('remote', 'rm', mirror, ignore_fail=True)
            git('remote', 'add', mirror, mirror_url % app)
            git('fetch', '--quiet', mirror, ignore_fail=True)
        git('fetch', '--quiet', 'origin')
        # Ensure we aren't on the branch we want to -B
        git('checkout', '--quiet', 'origin/%s' % branch)
        git('checkout', '--quiet', 'origin/%s' % branch, '-B', branch)


def deploy_settings_location():
    '''Figure out where we should put deploy_settings'''
    paths = yodeploy.config.deploy_config_paths()
    for path in paths:
        if os.path.exists(path):
            return path
    return paths[0]


def deploy_settings():
    '''Return deploy_settings'''
    return yodeploy.config.load_settings(deploy_settings_location())


def bootstrap_virtualenv(cmd):
    '''
    Bootstrap a virtualenv
    cmd specifies the location of virtualenv.py
    '''
    check_call((cmd, 'bootstrap_ve'))

    packages = []
    with open('requirements.txt') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                continue
            packages.append(line)

    check_call(['bootstrap_ve/bin/python',
                'bootstrap_ve/bin/easy_install',
                '-i', deploy_settings().build.pypi,
               ] + packages)


def find_required_version(package):
    '''See what version of packages was requested in requirements.txt'''
    with open('requirements.txt') as f:
        for line in f:
            line = line.strip()
            if line.startswith('%s==' % package):
                return line.split('=', 2)[-1]
    raise Exception('%s is not listed in requirements.txt' % package)


def urlopener_with_auth(url):
    '''
    Given a URL, return the URL with auth stripped, and a urlopener that can
    open it.
    Uses urllib2, so SSL certs aren't verified.
    '''
    opener = urllib2.build_opener()
    parsed = urlparse.urlparse(url)
    if parsed.username and parsed.password:
        host = parsed.hostname
        if parsed.port:
            host += ':%i' % parsed.port
        stripped_auth = (parsed[0], host) + parsed[2:]
        url = urlparse.urlunparse(stripped_auth)

        passwd_mgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
        base_url = urlparse.urlunparse((parsed[0], host, '', '', '', ''))
        passwd_mgr.add_password(realm=None, uri=base_url,
                                user=parsed.username, passwd=parsed.password)
        auth_handler = urllib2.HTTPBasicAuthHandler(passwd_mgr)
        opener = urllib2.build_opener(auth_handler)
    return url, opener


def get_from_pypi(app, version, pypi='https://pypi.python.org/simple/'):
    '''
    Really simple PyPI client.
    Downloads to CWD.
    '''
    expected_name = '%s-%s.tar.gz' % (app, version)
    if os.path.isfile(expected_name):
        return expected_name

    log.debug('Searching for %s==%s on %s', app, version, pypi)

    pypi, opener = urlopener_with_auth(pypi)
    href_re = re.compile(r'<a href="(.+?)">')
    f = opener.open(os.path.join(pypi, app))
    try:
        for match in href_re.finditer(f.read()):
            path = match.group(1).split('#', 1)[0]
            name = os.path.basename(path)
            if name == expected_name:
                url = urlparse.urljoin(pypi, path)
                break
        else:
            raise Exception('%s version %s not found on PyPI' % (app, version))
    finally:
        f.close()

    log.debug('Downloading %s', url)
    f_in = opener.open(url)
    try:
        with open(expected_name, 'w') as f_out:
            shutil.copyfileobj(f_in, f_out)
    finally:
        f_in.close()

    return expected_name


def build_virtualenv():
    '''Build a virtualenv for CWD, bootstrapping if necessary'''
    # Already bootstrapped
    if call(('build-virtualenv',)) == 0:
        return

    # Has a virtualenv built by hand
    if call(('virtualenv/bin/python',
             '-m', 'yodeploy.cmds.build_virtualenv')) == 0:
        return

    # Bootstrap a virtualenv with easy_install
    if binary_available('virtualenv'):
        bootstrap_virtualenv('virtualenv')
    else:
        version = find_required_version('virtualenv')
        pypi = deploy_settings().build.pypi
        fn = get_from_pypi('virtualenv', version, pypi)
        tar = tarfile.open(fn)
        tar.extractall()
        tar.close()
        os.unlink(fn)
        virtualenv_py = 'virtualenv-%s/virtualenv.py' % version
        os.chmod(virtualenv_py, 0755)
        bootstrap_virtualenv(virtualenv_py)
        shutil.rmtree('virtualenv-%s' % version)

    # Use the bootstrapped virtualenv to build_virtualenv
    check_call(('bootstrap_ve/bin/python', '-m',
                'yodeploy.cmds.build_virtualenv'))
    shutil.rmtree('bootstrap_ve')


def write_wrapper(script, ve, args=None):
    '''Install a wrapper for script in ~/bin'''
    name = os.path.basename(script).rsplit('.', 1)[0].replace('_', '-')
    wrapper_name = os.path.join(os.path.expanduser('~/bin'), name)
    if args:
        script = ' '.join([script] + list(args))
    with open(wrapper_name, 'w') as f:
        f.write('#!/bin/sh\nexec %s %s "$@"\n' % (ve, script))
    os.chmod(wrapper_name, 0755)


def setup_deployconfigs(yola_src):
    '''Configure deployconfigs'''
    # Create hostname.py
    configs = os.path.join(yola_src, 'deployconfigs', 'configs')
    hostname_py = os.path.join(configs, 'hostname.py')
    sample = os.path.join(configs, 'hostname.sample.py')
    if not os.path.exists(hostname_py):
        shutil.copyfile(sample, hostname_py)

    # Create yodeploy.conf
    deploy_settings_fn = deploy_settings_location()
    if not os.path.exists(deploy_settings_fn):
        dir_ = os.path.dirname(deploy_settings_fn)
        if not os.path.exists(dir_):
            os.makedirs(dir_)

        shutil.copyfile(os.path.join(yola_src, 'deployconfigs', 'other',
                                     'yodeploy.conf.py'),
                        deploy_settings_fn)


def setup_yodeploy(yola_src):
    '''Configure yodeploy'''
    root = os.path.join(yola_src, 'yodeploy')
    with chdir(root):
        build_virtualenv()

    # Install wrapper scripts
    ve = os.path.join(root, 'virtualenv', 'bin', 'python')
    for fn in os.listdir(os.path.join(root, 'yodeploy', 'cmds')):
        if fn.startswith('_') or fn.endswith('.pyc'):
            continue
        script = os.path.join(root, 'yodeploy', 'cmds', fn)
        write_wrapper(script, ve)


def setup_yoconfigurator(yola_src):
    '''Configure yoconfigurator'''
    root = os.path.join(yola_src, 'yoconfigurator')
    with chdir(root):
        build_virtualenv()

    # Install our single wrapper script
    ve = os.path.join(root, 'virtualenv', 'bin', 'python')
    script = os.path.join(root, 'bin', 'configurator.py')
    args = ('-d', os.path.join(yola_src, 'deployconfigs', 'configs'))
    write_wrapper(script, ve, args)


def main():
    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      default=False, action='store_true',
                      help='Increase verbosity')
    parser.add_option('-b', '--branch',
                      metavar='APP BRANCH', nargs=2,
                      default=[], action='append',
                      help='Check out BRANCH of APP instead of master '
                           '(can be specified multiple times)')
    parser.add_option('--skip-clones',
                      default=False, action='store_true',
                      help='Skip cloning repositories, everything is already '
                           'checked out, I promise')
    opts, args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if opts.verbose else logging.INFO)

    yola_src = check_environment()

    apps = ('deployconfigs', 'yodeploy', 'yoconfigurator')
    if not opts.skip_clones:
        branches = dict((app, 'master') for app in apps)
        branches.update(dict(opts.branch))
        for app in apps:
            clone(app, yola_src, branches[app])

    for app in apps:
        setup = globals()['setup_%s' % app]
        setup(yola_src)


if __name__ == '__main__':
    main()
