#!/usr/bin/env python
from __future__ import print_function

import argparse
from cgi import parse_header
import json
import os
import stat
import sys

import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from yodeploy import config  # noqa

list_path = 'envs/list/'
cert_path = 'envs/certificate/public'
key_path = 'envs/certificate/private'


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


def get_certificate(url, name, username, password):
    cert_url = url + '/'.join([cert_path, name])
    cert = requests.get(cert_url, auth=HTTPBasicAuth(username, password))
    return cert


def get_private_key(url, name, username, password):
    cert_url = url + '/'.join([key_path, name])
    cert = requests.get(cert_url, auth=HTTPBasicAuth(username, password))
    return cert


def get_env_list(url, username, password):
    list_url = ''.join([url, list_path])
    envs = requests.get(list_url, auth=HTTPBasicAuth(username, password))
    return envs


def get_filename_from_headers(headers, fallback):
    content_dispostion = headers.get('Content-Disposition', '')
    _, params = parse_header(content_dispostion)

    if '/' in params.get('filename', ''):
        return fallback

    return params.get('filename', fallback)


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
    username = settings.envhub.user
    password = settings.envhub.password
    url = settings.envhub.url

    if options.list:
        env_response = get_env_list(url, username, password)
        if env_response.status_code != 200:
            print('failed to retrieve envs with status'
                  '{response.status_code}\n{response.content}'.format(
                        response=env_response))
            sys.exit(1)
        for env in json.loads(env_response.content):
            print(env['name'], env['developer'])
        return

    if options.clean:
        clean_ssl_directory(settings)

    if options.install:
        name = options.install
        cert_response = get_certificate(url, name, username, password)
        key_response = get_private_key(url, name, username, password)

        ssl_dir = find_ssl_path(settings)
        cert_local_path = os.path.join(ssl_dir, 'certs')
        pk_local_path = os.path.join(ssl_dir, 'private')

        cert_filename = get_filename_from_headers(
            cert_response.headers, '%s.pem' % name)
        pk_filename = get_filename_from_headers(
            key_response.headers, '%s.key' % name)
        cert_local_path = os.path.join(cert_local_path, cert_filename)
        pk_local_path = os.path.join(pk_local_path, pk_filename)

        with open(cert_local_path, 'w') as fn:
            fn.write(cert_response.content)
            print('certificate saved as {}'.format(cert_local_path))

        with open(pk_local_path, 'w') as fn:
            fn.write(key_response.content)
            print('private key saved as {}'.format(pk_local_path))


if __name__ == '__main__':
    main()
