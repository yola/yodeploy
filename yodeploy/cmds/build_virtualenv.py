#!/usr/bin/env python
from __future__ import print_function
import argparse
import logging
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from yodeploy import virtualenv
import yodeploy.config
import yodeploy.repository
import yodeploy.util


log = logging.getLogger(os.path.basename(__file__).rsplit('.', 1)[0])


def main():
    parser = argparse.ArgumentParser(
        description="Prepares virtualenv bundles. If a virtualenv with the "
        "right hash already exists in the store, it'll be downloaded and "
        "extracted, unless --force is specified.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-c', '--config', metavar='FILE',
                        default=yodeploy.config.find_deploy_config(False),
                        help='Location of the Deploy configuration file.')
    parser.add_argument('-a', '--app', metavar='NAME',
                        default=os.path.basename(os.getcwd()),
                        help='Application name')
    parser.add_argument('--target', metavar='TARGET',
                        default='master',
                        help='Target to store/retrieve virtualenvs from')
    parser.add_argument('--hash',
                        action='store_true',
                        help="Only determine the virtualenv's id")
    parser.add_argument('-u', '--upload',
                        action='store_true',
                        help="Upload the resultant virtualenv to the "
                             "repository, if there isn't one of this id "
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
    parser.add_argument('-r', '--requirement', metavar='FILE',
                        default='requirements.txt',
                        help='Install from the given requirements file.')
    parser.add_argument('--compat', metavar='LEVEL', type=int,
                        help='Assume the specified compat level. '
                             '(Defaults to reading deploy/compat)')

    options = parser.parse_args()
    if not os.path.isfile(options.requirement):
        parser.error('%s does not exist' % options.requirement)

    if options.config is None:
        # Yes, it was a default, but we want to prent the error
        options.config = yodeploy.config.find_deploy_config()

    if not options.hash and (options.download or options.upload):
        if not options.app:
            parser.error('Application name must be specified')

    if options.verbose:
        logging.basicConfig(level=logging.DEBUG, stream=sys.stderr)
    else:
        logging.basicConfig(level=logging.INFO, stream=sys.stderr)

    deploy_settings = yodeploy.config.load_settings(options.config)
    repository = yodeploy.repository.get_repository(deploy_settings)

    if not options.compat:
        try:
            with open('deploy/compat') as f:
                options.compat = int(f.read())
        except IOError:
            options.compat = yodeploy.util.infer_compat_version()

    python_version = virtualenv.get_python_version(options.compat)
    platform = deploy_settings.artifacts.platform
    ve_id = virtualenv.get_id(options.requirement, python_version, platform)
    if options.hash:
        print(ve_id)
        return

    existing_ve = os.path.exists('virtualenv')
    if os.path.exists('virtualenv/.hash'):
        with open('virtualenv/.hash', 'r') as f:
            existing_ve = f.read().strip()

    if existing_ve:
        if existing_ve == ve_id and not options.force:
            log.info('Existing virtualenv matches requirements.txt')
            options.download = False
        else:
            shutil.rmtree('virtualenv')

    if options.download:
        downloaded = False
        try:
            virtualenv.download_ve(
                repository, options.app, ve_id, options.target)
            downloaded = True
        except KeyError:
            log.warn('No existing virtualenv, building...')
        if downloaded:
            options.upload = False
            yodeploy.util.extract_tar('virtualenv.tar.gz', 'virtualenv')

    if not os.path.isdir('virtualenv'):
        virtualenv.create_ve(
            '.', python_version, platform,
            pypi=deploy_settings.build.pypi,
            req_file=options.requirement)

    if options.upload:
        virtualenv.upload_ve(
            repository, options.app, ve_id,
            options.target, overwrite=options.force)


if __name__ == '__main__':
    main()
