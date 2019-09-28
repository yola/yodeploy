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

# overrwrite the unsafe python 2 input method with raw_input, which does not
# eval user input. In Python 3, raw_input has been renamed to input. This
# assignment will raise a NameError, doing nothing.
try:
    input = raw_input
except NameError:
    pass


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


def get_files(*paths):
    for path in paths:
        for f in os.listdir(path):
            full_path = os.path.join(path, f)

            if os.path.isfile(full_path):
                yield full_path


def remove_all_files(files):
    for file in files:
        print('removing {}'.format(file))
        os.unlink(file)


def clean_ssl_directory(settings, confirm=True):
    ssl_dir = os.path.expanduser(settings.yodeploy.ssl_path)
    certs_dir = os.path.join(ssl_dir, 'certs')
    private_dir = os.path.join(ssl_dir, 'private')
    clean_message = '{} and {} are clean.'.format(certs_dir, private_dir)

    # Take care here not to generate this list before and again after the
    # confirmation prompt. If one were to do so and a file was written to a
    # target directory before the remove operation executed, we would end up
    # removing something the user hadn't approved
    to_remove = list(get_files(certs_dir, private_dir))

    if not to_remove:
        print(clean_message)
        return

    if confirm:
        for f in to_remove:
            print(f)

    while confirm:
        response = input('Do you want to delete these files? (y/n) ')
        response = response.lower()

        if response == 'y':
            break

        if response == 'n':
            return

    remove_all_files(to_remove)

    print(clean_message)


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
    parser.add_argument(
        '--no-input', action='store_true', help='Do not ask for confirmation.')
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
        clean_ssl_directory(settings, confirm=not options.no_input)

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
