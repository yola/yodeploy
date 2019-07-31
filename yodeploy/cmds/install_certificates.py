#!/usr/bin/env python
import argparse
import json
import os
import re
import sys

import requests
from requests.auth import HTTPBasicAuth

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from yodeploy import config

_SSL_CERT_PATH = '/etc/ssl/certs'
_SSL_PRIVATE_KEY_PATH = '/etc/ssl/private'

list_path = 'envs/list/'
cert_path = 'envs/certificate/public'
key_path = 'envs/certificate/private'


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
    parser.add_argument('--certificate-path', default=_SSL_CERT_PATH)
    parser.add_argument('--private-key-path', default=_SSL_PRIVATE_KEY_PATH)

    options = parser.parse_args()

    deploy_config = config.find_deploy_config()
    settings = config.load_settings(deploy_config)
    username = settings.envhub.user
    password = settings.envhub.password
    url = settings.envhub.url

    if options.list:
        env_response = get_env_list(url, username, password)
        if env_response.status_code != 200:
            print 'failed to retrieve envs with status' \
                  '{response.status_code}\n{response.content}'.format(
                    response=env_response)
            return
        for env in json.loads(env_response.content):
            print env['name'], env['developer']
        return

    if options.install:
        name = options.install
        cert_response = get_certificate(url, name, username, password)
        key_response = get_private_key(url, name, username, password)

        cert_local_path = options.certificate_path
        pk_local_path = options.private_key_path

        cert_download_fn = re.findall(
            'filename=(.+)', cert_response.headers['Content-Disposition'])[0]
        cert_local_fn = os.path.join(cert_local_path, cert_download_fn)
        with open(cert_local_fn, 'w+') as fn:
            fn.write(cert_response.content)
            fn.close()
            print 'certificate saved as {}'.format(cert_local_fn)

        pk_download_fn = re.findall(
            'filename=(.+)', key_response.headers['Content-Disposition'])[0]
        pk_local_fn = os.path.join(pk_local_path, pk_download_fn)
        with open(pk_local_fn, 'w+') as fn:
            fn.write(key_response.content)
            fn.close()
            print 'private key saved as {}'.format(pk_local_fn)


if __name__ == '__main__':
    main()
