#!/usr/bin/env python

# This downloads the latest builds from S3
# It's entirely self-contained because we bundle it in a Chef recipe

import base64
import email.utils
import hashlib
import hmac
import imp
import logging
import optparse
import os
import shutil
import subprocess
import sys
import sysconfig
import tarfile


try:  # python 3
    from urllib.request import Request, urlopen
    from urllib.parse import urlparse
except ImportError:  # python 2
    from urllib2 import Request, urlopen
    from urlparse import urlparse


deploy_settings_fn = '/etc/yola/deploy.conf.py'
deploy_base = '/srv'
log = logging.getLogger('bootstrap')


class S3Client(object):
    '''A really simple, NIH, pure-python S3 client'''
    def __init__(self, bucket, access_key, secret_key):
        self.bucket = bucket

        # Coerce keys to byte strings for safe use in hashing functions
        try:
            self.access_key = access_key.encode()
        except AttributeError:
            self.access_key = access_key

        try:
            self.secret_key = secret_key.encode()
        except AttributeError:
            self.secret_key = secret_key

    def get(self, key):
        url = 'https://s3.amazonaws.com/%s/%s' % (self.bucket, key)
        log.debug('Downloading %s', url)
        req = Request(url)
        req.add_header('Date', email.utils.formatdate())
        self._sign_req(req)
        return urlopen(req)

    def _sign_req(self, req):
        # We don't bother with CanonicalizedAmzHeaders
        assert not [True for header in req.headers
                    if header.lower().startswith('x-amz-')]
        cleartext = [req.get_method(),
                     req.get_header('Content-MD5', ''),
                     req.get_header('Content-Type', ''),
                     req.get_header('Date', ''),
                     urlparse(req.get_full_url()).path]
        cleartext = '\n'.join(cleartext)
        cleartext = cleartext.encode()

        mac = hmac.new(self.secret_key, cleartext, hashlib.sha1)
        signature = base64.encodestring(mac.digest()).rstrip()

        req.add_header('Authorization',
                       b'AWS %s:%s' % (self.access_key, signature))


# stolen from yodeploy.config

def load_settings(fn):
    '''
    Load deploy_settings from the specified filename
    '''
    fake_mod = '_deploy_settings'
    description = ('.py', 'r', imp.PY_SOURCE)
    with open(fn) as f:
        m = imp.load_module(fake_mod, f, fn, description)
    return m.deploy_settings


# stolen from yodeploy.virtualenv

def sha224sum(filename):
    m = hashlib.sha224()
    with open(filename, 'rb') as f:
        m.update(f.read())
    return m.hexdigest()


def get_id(filename, platform):
    """Calculate the ID of a virtualenv for the given requirements.txt"""
    req_hash = sha224sum(filename)
    return '%s-%s-%s' % (sysconfig.get_python_version(), platform, req_hash)


# stolen from yodeploy.util

def extract_tar(tarball, root):
    '''Ensure that tarball only has one root directory.
    Extract it into the parent directory of root, and rename the extracted
    directory to root.
    '''
    workdir = os.path.dirname(root)
    tar = tarfile.open(tarball, 'r')
    try:
        members = tar.getmembers()
        for member in members:
            member.uid = 0
            member.gid = 0
            member.uname = 'root'
            member.gname = 'root'
        roots = set(member.name.split('/', 1)[0] for member in members)
        if len(roots) > 1:
            raise ValueError("Tarball has > 1 top-level directory")
        tar.extractall(workdir, members)
    finally:
        tar.close()

    extracted_root = os.path.join(workdir, list(roots)[0])
    os.rename(extracted_root, root)


# Local functions

def mkdir_and_extract_tar(tarball, destination):
    '''Extract a tarball to destination'''
    parent = os.path.dirname(destination)
    if not os.path.exists(parent):
        os.makedirs(parent)
    elif os.path.exists(destination):
        shutil.rmtree(destination)
    extract_tar(tarball, destination)


def app_path(*args, **kwargs):
    '''Convenience function for joining paths to /srv/yodeploy'''
    app = kwargs.pop('app', 'yodeploy')
    assert not kwargs
    return os.path.join(deploy_base, app, *args)


def get_latest(s3, app, target, artifact, destination):
    '''
    Grab the latest version of an artifact from an S3 yodeploy repository
    '''
    parent = os.path.dirname(destination)
    if not os.path.exists(parent):
        os.makedirs(parent)
    f = s3.get(os.path.join(app, target, artifact, 'latest'))
    try:
        version = f.read().decode('utf8').rstrip()
    finally:
        f.close()
    try:
        f1 = s3.get(os.path.join(app, target, artifact, version))
        with open(destination, 'wb') as f2:
            shutil.copyfileobj(f1, f2)
    finally:
        f1.close()
    return version


def get_app(s3, target):
    '''Grab and unpack the app'''
    log.info('Downloading the app tarball')
    tarball = app_path('versions', 'unpack', 'yodeploy.tar.gz')
    version = get_latest(s3, 'yodeploy', target, 'yodeploy.tar.gz',
                         tarball)

    log.info('Extracting the app tarball')
    mkdir_and_extract_tar(tarball, app_path('versions', version))
    return version


def get_deploy_ve(s3, target, version, platform):
    '''Grab and unpack the deploy virtualenv'''
    ve_id = get_id(
        app_path('versions', version, 'deploy', 'requirements.txt'),
        platform)
    tarball_name = 'virtualenv-%s.tar.gz' % ve_id
    log.info('Downloading the deploy virtualenv tarball')
    tarball = app_path('virtualenvs', 'unpack', tarball_name, app='deploy')
    get_latest(s3, 'deploy', target, tarball_name, tarball)

    log.info('Extracting the deploy virtualenv tarball')
    mkdir_and_extract_tar(tarball, app_path('virtualenvs', ve_id,
                                            app='deploy'))
    return ve_id


def hook(hook_name, version, target, dve_id):
    '''Call deploy hooks'''
    log.info('Calling hook: %s', hook_name)
    deploy_python = app_path('virtualenvs', dve_id, 'bin', 'python',
                             app='deploy')

    with open(app_path('versions', version, 'deploy', 'compat')) as f:
        compat = int(f.read())
    if compat == 3:
        module = 'yola.deploy.__main__'
    elif compat == 4:
        module = 'yodeploy.__main__'

    subprocess.check_call((deploy_python,
                           '-m', module,
                           '--config', deploy_settings_fn,
                           '--app', 'yodeploy',
                           '--hook', hook_name,
                           '--target', target,
                           app_path(), version))


def main():
    global deploy_base

    default_target = 'master'
    deploy_settings = None
    if os.path.exists(deploy_settings_fn):
        deploy_settings = load_settings(deploy_settings_fn)
        default_target = deploy_settings.artifacts.target
        deploy_base = deploy_settings.paths.apps

    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      default=False, action='store_true',
                      help='Increase verbosity')
    parser.add_option('-t', '--target', default=default_target,
                      help='Get yodeploy from the specified target')
    opts, args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if opts.verbose else logging.INFO)

    if deploy_settings is None:
        log.error("Couldn't find deploy settings: %s", deploy_settings_fn)
        sys.exit(1)

    if os.path.exists(app_path('live')):
        log.error('%s already exists', app_path('live'))
        sys.exit(1)

    if deploy_settings.artifacts.store != 's3':
        log.error('Only bootstrapping from S3 is supported, not %s',
                  deploy_settings.artifacts.store)
        sys.exit(1)

    s3 = S3Client(deploy_settings.artifacts.store_settings.s3.bucket,
                  deploy_settings.artifacts.store_settings.s3.access_key,
                  deploy_settings.artifacts.store_settings.s3.secret_key)

    log.info('Bootstrapping yodeploy')
    version = get_app(s3, opts.target)
    ve_id = get_deploy_ve(
        s3, opts.target, version, deploy_settings.artifacts.platform)
    hook('prepare', version, opts.target, ve_id)
    os.symlink('versions/%s' % version, app_path('live'))
    hook('deployed', version, opts.target, ve_id)


if __name__ == '__main__':
    main()
