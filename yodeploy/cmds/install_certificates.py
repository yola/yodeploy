#!/usr/bin/env python
from __future__ import print_function

import argparse
from cgi import parse_header
import os
import stat
import sys

from demands import HTTPServiceClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from yodeploy import config  # noqa


class CertificateService(HTTPServiceClient):
    def _get_filename_from_headers(self, headers, fallback):
        content_dispostion = headers.get('Content-Disposition', '')
        _, params = parse_header(content_dispostion)

        if '/' in params.get('filename', ''):
            return fallback

        return params.get('filename', fallback)

    def get_certificate(self, env_name):
        filename = '%s.pem' % env_name

        response = self.get('/envs/certificate/public/{}/'.format(env_name))
        filename = self._get_filename_from_headers(response.headers, filename)

        return filename, response.content

    def get_private_key(self, env_name):
        filename = '%s.key' % env_name

        response = self.get('/envs/certificate/private/{}/'.format(env_name))
        filename = self._get_filename_from_headers(response.headers, filename)

        return filename, response.content

    def get_environments(self):
        return self.get('/envs/list/').json()


def find_ssl_path(settings):
    ssl_dir = os.path.expanduser(settings.yodeploy.ssl_path)
    certs_dir = os.path.join(ssl_dir, 'certs')
    private_dir = os.path.join(ssl_dir, 'private')
    if not os.path.exists(ssl_dir):
        os.makedirs(ssl_dir)
    if not os.path.exists(certs_dir):
        os.mkdir(certs_dir)
    if not os.path.exists(private_dir):
        os.mkdir(private_dir)
        os.chmod(private_dir, stat.S_IRWXU)
    return ssl_dir


def remove_all_files(path):
    for f in os.listdir(path):
        remove_path = os.path.join(path, f)
        if os.path.isfile(remove_path):
            print('removing {}'.format(remove_path))
            os.unlink(remove_path)


def clean_ssl_directory(settings):
    ssl_dir = os.path.expanduser(settings.yodeploy.ssl_path)
    certs_dir = os.path.join(ssl_dir, 'certs')
    private_dir = os.path.join(ssl_dir, 'private')
    remove_all_files(certs_dir)
    remove_all_files(private_dir)


def main():
    parser = argparse.ArgumentParser(
        description='Downloads ssl certificates from envhub and installs them '
                    'locally for development purposes.'
    )
    parser.add_argument('-l', '--list', action='store_true',
                        help='List instance_ids of running envs')
    parser.add_argument('-i', '--install',
                        help='Install ssl certificate for given instance name')
    parser.add_argument(
        '--clean', action='store_true',
        help='Deletes all ssl certificates in dir managed by this app')
    options = parser.parse_args()

    deploy_config = config.find_deploy_config()
    settings = config.load_settings(deploy_config)
    cert_service = CertificateService(
        settings.envhub.url,
        auth=(settings.envhub.user, settings.envhub.password))

    if options.list:
        for env in cert_service.get_environments():
            print('{name} -- {developer}'.format(**env))

    if options.clean:
        clean_ssl_directory(settings)

    if options.install:
        name = options.install
        cert_filename, cert = cert_service.get_certificate(name)
        key_filename, key = cert_service.get_private_key(name)

        ssl_dir = find_ssl_path(settings)
        cert_local_path = os.path.join(ssl_dir, 'certs')
        pk_local_path = os.path.join(ssl_dir, 'private')

        cert_local_path = os.path.join(cert_local_path, cert_filename)
        pk_local_path = os.path.join(pk_local_path, key_filename)

        with open(cert_local_path, 'w') as fn:
            fn.write(cert)
            print('certificate saved as {}'.format(cert_local_path))

        with open(pk_local_path, 'w') as fn:
            fn.write(key)
            print('private key saved as {}'.format(pk_local_path))


if __name__ == '__main__':
    main()
