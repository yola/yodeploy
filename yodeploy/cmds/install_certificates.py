#!/usr/bin/env python
from __future__ import print_function

import argparse
import json
import os
import re
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
    ssl_dir = os.path.expanduser(settings.common.yodeploy.ssl_path)
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


def main():
    parser = argparse.ArgumentParser(
        description='Downloads ssl certificates from envhub and installs them '
                    'locally for development purposes.'
    )
    parser.add_argument('-l', '--list', action='store_true',
                        help='List instance_ids of running envs')
    parser.add_argument('-i', '--install',
                        help='Install ssl certificate for given instance name')

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

    if options.install:
        name = options.install
        cert_response = get_certificate(url, name, username, password)
        key_response = get_private_key(url, name, username, password)

        ssl_dir = find_ssl_path(settings)
        cert_local_path = os.path.join(ssl_dir, 'certs')
        pk_local_path = os.path.join(ssl_dir, 'private')

        cert_download_fn = re.findall(
            'filename=(.+)', cert_response.headers['Content-Disposition'])[0]
        if '/' not in cert_download_fn:
            cert_local_fn = os.path.join(cert_local_path, cert_download_fn)
        else:
            print('WARNING! Download filename contains /'
                  'defaulting to {}.crt'.format(name))
            cert_local_fn = os.path.join(
                cert_local_path, '{}.crt'.format(name))

        with open(cert_local_fn, 'w') as fn:
            fn.write(cert_response.content)
            print('certificate saved as {}'.format(cert_local_fn))

        pk_download_fn = re.findall(
            'filename=(.+)', key_response.headers['Content-Disposition'])[0]
        if '/' not in cert_download_fn:
            pk_local_fn = os.path.join(pk_local_path, pk_download_fn)
        else:
            print('WARNING! Download filename contains /'
                  'defaulting to {}.key'.format(name))
            pk_local_fn = os.path.join(
                pk_local_path, '{}.key'.format(name))

        with open(pk_local_fn, 'w') as fn:
            fn.write(key_response.content)
            print('private key saved as {}'.format(pk_local_fn))


if __name__ == '__main__':
    main()
