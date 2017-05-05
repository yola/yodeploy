#!/usr/bin/env python
from __future__ import print_function
import argparse
import json
import logging
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import yodeploy.config
import yodeploy.repository

# Replaced when configured
log = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
            description='Manage artifacts in a repository')
    subparsers = parser.add_subparsers(dest='command',
                                       title='commands',
                                       help='additional help')

    upload_p = subparsers.add_parser('upload',
                                     help='Upload a file to the repository')
    upload_p.add_argument('app', help='The application name')
    upload_p.add_argument('filename', help='The file to upload')
    upload_p.add_argument('version', help='Version for uploaded file')
    upload_p.add_argument('--target', metavar='TARGET',
                          default='master',
                          help='The target to upload to')
    upload_p.add_argument('-m', '--meta', metavar='FILE',
                          help='File containing JSON metadata')
    upload_p.add_argument('--save-as', metavar='FILE',
                          help='Upload as FILE (Default: filename)')

    download_p = subparsers.add_parser('download',
            help='Download a file from the repository')
    download_p.add_argument('app', help='The application name')
    download_p.add_argument('filename', help='The file to download')
    download_p.add_argument('--target', metavar='TARGET',
                            default='master',
                            help='The target to download from')
    download_p.add_argument('--save-as', metavar='FILE',
                            help='Download to FILE (Default: same name in .)')
    download_p.add_argument('--version', metavar='VER',
                            help='Download version VER of the file')

    versions_p = subparsers.add_parser('versions',
            help='List the versions of a file in the repository')
    versions_p.add_argument('app', help='The application name')
    versions_p.add_argument('filename', nargs='?', help='The file to examine')
    versions_p.add_argument('--target', metavar='TARGET',
                            default='master',
                            help='The target to examine')

    subparsers.add_parser('list_apps', help='List apps in the repository')

    list_targets_p = subparsers.add_parser('list_targets',
            help='List targets in the repository')
    list_targets_p.add_argument('app', help='The application name')

    list_files_p = subparsers.add_parser('list_files',
            help='List files in the repository')
    list_files_p.add_argument('app', help='The application name')
    list_files_p.add_argument('--target', metavar='TARGET',
                              default='master',
                              help='The target to examine')

    gc_p = subparsers.add_parser('gc',
                                 help='Remove old artifacts')
    gc_p.add_argument('--max-versions', metavar='N',
                      type=int, default=2,
                      help='The most versions to leave behind')

    parser.add_argument('-d', '--debug', action='store_true',
                        help='Increase verbosity')
    parser.add_argument('-c', '--config', metavar='FILE',
                        default=yodeploy.config.find_deploy_config(False),
                        help='Location of the Deploy configuration file.')
    opts = parser.parse_args()

    if opts.config is None:
        # Yes, it was a default, but we want to prent the error
        opts.config = yodeploy.config.find_deploy_config()

    return opts


def configure_logging(verbose):
    "Set up logging"
    global log

    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    logging.getLogger('boto').setLevel(logging.WARNING)

    log = logging.getLogger(os.path.basename(__file__).rsplit('.', 1)[0])


def do_upload(opts, repository):
    "Upload a file to the repository"

    meta = None
    if opts.meta:
        with open(opts.meta, 'r') as f:
            meta = json.load(f)
    if not opts.save_as:
        opts.save_as = os.path.basename(opts.filename)
    with open(opts.filename, 'rb') as f:
        repository.put(opts.app, opts.version, f, meta, target=opts.target,
                       artifact=opts.save_as)


def do_download(opts, repository):
    "Download a file from the repository"

    if not opts.save_as:
        opts.save_as = opts.filename
    with repository.get(opts.app, opts.version, target=opts.target,
                        artifact=opts.filename) as f1:
        with open(opts.save_as, 'wb') as f2:
            shutil.copyfileobj(f1, f2)


def do_versions(opts, repository):
    "List the versions of a file in the repository"

    versions = repository.list_versions(opts.app, target=opts.target,
                                        artifact=opts.filename)
    if versions:
        print('\n'.join(versions))
    else:
        print('No versions found', file=sys.stderr)
        sys.exit(1)


def do_list_apps(opts, repository):
    "List apps in the repository"

    apps = repository.list_apps()
    if apps:
        print('\n'.join(apps))
    else:
        print('No apps found', file=sys.stderr)
        sys.exit(1)


def do_list_targets(opts, repository):
    "List targets in the repository"

    targets = repository.list_targets(opts.app)
    if targets:
        print('\n'.join(targets))
    else:
        print('No targets found', file=sys.stderr)
        sys.exit(1)


def do_list_files(opts, repository):
    "List files in the repository"

    artifacts = repository.list_artifacts(opts.app, target=opts.target)
    if artifacts:
        print('\n'.join(artifacts))
    else:
        print('No files found', file=sys.stderr)
        sys.exit(1)


def do_gc(opts, repository):
    """Clean up the repository"""

    repository.gc(max_versions=opts.max_versions)


def main():
    "Dispatch"
    opts = parse_args()
    configure_logging(opts.debug)
    deploy_settings = yodeploy.config.load_settings(opts.config)

    repository = yodeploy.repository.get_repository(deploy_settings)

    cmd = globals().get('do_%s' % opts.command.replace('-', '_'))
    if cmd:
        cmd(opts, repository)
    else:
        log.error('Unsupported command: %s', opts.command)
        sys.exit(1)


if __name__ == '__main__':
    main()
