#!/usr/bin/env python

# yola.deploy should normally be bootstrapped with Chef, but if you need to do
# it by hand, here you go.
# This downloads the latest builds from S3

import base64
import email.utils
import hashlib
import hmac
import logging
import optparse
import os
import shutil
import subprocess
import sys
import urllib2
import urlparse

sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import yola.deploy.config
import yola.deploy.util
from yola.deploy.virtualenv import ve_version, sha224sum

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


def deploy_settings_location():
    '''Figure out where we should put deploy_settings'''
    paths = yola.deploy.config.deploy_config_paths()
    for path in paths:
        if os.path.exists(path):
            return path
    return paths[0]


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


def extract_tar(tarball, destination):
    '''Extract a tarball to destination'''
    parent = os.path.dirname(destination)
    if not os.path.exists(parent):
        os.makedirs(parent)
    elif os.path.exists(destination):
        shutil.rmtree(destination)
    yola.deploy.util.extract_tar(tarball, destination)


def get_app(s3, target):
    '''Grab and unpack the app'''
    log.info('Downloading the app tarball')
    tarball = app_path('versions', 'unpack', 'yola.deploy.tar.gz')
    version = get_latest(s3, 'yola.deploy', target, 'yola.deploy.tar.gz',
                         tarball)

    log.info('Extracting the app tarball')
    extract_tar(tarball, app_path('versions', version))
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
    extract_tar(tarball, app_path('virtualenvs', ve_name, app='deploy'))
    return ve_name


def hook(hook_name, version, target, dve_name):
    '''Call deploy hooks'''
    log.info('Calling hook: %s', hook_name)
    deploy_python = app_path('virtualenvs', dve_name, 'bin', 'python',
                             app='deploy')
    subprocess.check_call((deploy_python,
                           '-m', 'yola.deploy.__main__',
                           '--config', deploy_settings_location(),
                           '--app', 'yola.deploy',
                           '--hook', hook_name,
                           '--target', target,
                           app_path(), version))


def main():
    global deploy_base

    deploy_settings_fn = deploy_settings_location()
    default_target = 'master'
    deploy_settings = None
    if os.path.exists(deploy_settings_fn):
        deploy_settings = yola.deploy.config.load_settings(deploy_settings_fn)
        default_target = deploy_settings.artifacts.target
        deploy_base = deploy_settings.paths.apps

    parser = optparse.OptionParser()
    parser.add_option('-v', '--verbose',
                      default=False, action='store_true',
                      help='Increase verbosity')
    parser.add_option('-t', '--target', default=default_target,
                      help='Get yola.depoly from the spcefied target')
    opts, args = parser.parse_args()
    logging.basicConfig(level=logging.DEBUG if opts.verbose else logging.INFO)

    if deploy_settings is None:
        log.error("Couldn't find deploy settings")
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
