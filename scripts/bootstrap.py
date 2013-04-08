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
import tarfile
import urllib2
import urlparse


deploy_settings_fn = '/etc/yola/deploy.conf.py'
deploy_base = '/srv'
log = logging.getLogger('bootstrap')


class S3Client(object):
    '''A really simple, NIH, pure-python S3 client'''
    def __init__(self, bucket, access_key, secret_key):
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key

    def get(self, key):
        url = 'https://s3.amazonaws.com/%s/%s' % (self.bucket, key)
        log.debug('Downloading %s', url)
        req = urllib2.Request(url)
        req.add_header('Date', email.utils.formatdate())
        self._sign_req(req)
        return urllib2.urlopen(req)

    def _sign_req(self, req):
        # We don't bother with CanonicalizedAmzHeaders
        assert not [True for header in req.headers
                    if header.lower().startswith('x-amz-')]
        cleartext = [req.get_method(),
                     req.get_header('Content-MD5', ''),
                     req.get_header('Content-Type', ''),
                     req.get_header('Date', ''),
                     urlparse.urlparse(req.get_full_url()).path]
        cleartext = '\n'.join(cleartext)

        mac = hmac.new(self.secret_key, cleartext, hashlib.sha1)
        signature = base64.encodestring(mac.digest()).rstrip()

        req.add_header('Authorization',
                       'AWS %s:%s' % (self.access_key, signature))


# stolen from yola.deploy.config

def load_settings(fn):
    '''
    Load deploy_settings from the specified filename
    '''
    fake_mod = '_deploy_settings'
    description = ('.py', 'r', imp.PY_SOURCE)
    with open(fn) as f:
        m = imp.load_module(fake_mod, f, fn, description)
    return m.deploy_settings


# stolen from yola.deploy.virtualenv

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


def sha224sum(filename):
    m = hashlib.sha224()
    with open(filename) as f:
        m.update(f.read())
    return m.hexdigest()


def ve_version(req_hash):
    return '%s-%s-%s' % (sysconfig.get_python_version(),
                         sysconfig.get_platform(),
                         req_hash)


# stolen from yola.deploy.util

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
    '''Convenience function for joining paths to /srv/yola.deploy'''
    app = kwargs.pop('app', 'yola.deploy')
    assert not kwargs
    return os.path.join(deploy_base, app, *args)


def get_latest(s3, app, target, artifact, destination):
    '''
    Grab the latest version of an artifact from an S3 yola.deploy repository
    '''
    parent = os.path.dirname(destination)
    if not os.path.exists(parent):
        os.makedirs(parent)
    f = s3.get(os.path.join(app, target, artifact, 'latest'))
    try:
        version = f.read().rstrip()
    finally:
        f.close()
    try:
        f1 = s3.get(os.path.join(app, target, artifact, version))
        with open(destination, 'w') as f2:
            shutil.copyfileobj(f1, f2)
    finally:
        f1.close()
    return version


def get_app(s3, target):
    '''Grab and unpack the app'''
    log.info('Downloading the app tarball')
    tarball = app_path('versions', 'unpack', 'yola.deploy.tar.gz')
    version = get_latest(s3, 'yola.deploy', target, 'yola.deploy.tar.gz',
                         tarball)

    log.info('Extracting the app tarball')
    mkdir_and_extract_tar(tarball, app_path('versions', version))
    return version


def get_deploy_ve(s3, target, version):
    '''Grab and unpack the deploy virtualenv'''
    ve_name = ve_version(sha224sum(app_path('versions', version, 'deploy',
                                            'requirements.txt')))
    tarball_name = 'virtualenv-%s.tar.gz' % ve_name
    log.info('Downloading the deploy virtualenv tarball')
    tarball = app_path('virtualenvs', 'unpack', tarball_name, app='deploy')
    get_latest(s3, 'deploy', target, tarball_name, tarball)

    log.info('Extracting the deploy virtualenv tarball')
    mkdir_and_extract_tar(tarball, app_path('virtualenvs', ve_name,
                                            app='deploy'))
    return ve_name


def hook(hook_name, version, target, dve_name):
    '''Call deploy hooks'''
    log.info('Calling hook: %s', hook_name)
    deploy_python = app_path('virtualenvs', dve_name, 'bin', 'python',
                             app='deploy')
    subprocess.check_call((deploy_python,
                           '-m', 'yola.deploy.__main__',
                           '--config', deploy_settings_fn,
                           '--app', 'yola.deploy',
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
                      help='Get yola.deploy from the specified target')
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

    log.info('Bootstrapping yola.deploy')
    version = get_app(s3, opts.target)
    ve_name = get_deploy_ve(s3, opts.target, version)
    hook('prepare', version, opts.target, ve_name)
    os.symlink('versions/%s' % version, app_path('live'))
    hook('deployed', version, opts.target, ve_name)


if __name__ == '__main__':
    main()
