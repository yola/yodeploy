#!/usr/bin/env python

import argparse
import copy
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import yola.deploy.config
import yola.deploy.repository


def parse_args():
    parser = argparse.ArgumentParser(
            description='Build and upload an artifact')
    parser.add_argument('app', help='The application name')
    parser.add_argument('-T', '--skip-tests', action='store_true',
                          help="Don't run tests")
    parser.add_argument('--target', default='master',
                          help='The target to upload to')
    parser.add_argument('-c', '--config', metavar='FILE',
                        default=yola.deploy.config.find_deploy_config(False),
                        help='Location of the Deploy configuration file.')
    opts = parser.parse_args()

    if opts.config is None:
        # Yes, it was a default, but we want to prent the error
        opts.config = yola.deploy.config.find_deploy_config()

    return opts


def main():
    opts = parse_args()

    with open('deploy/compat') as f:
        if f.read().strip() != '3':
            print >> sys.stderr, 'Only deploy compat 3 apps are supported'
            sys.exit(1)

    python = os.path.abspath(sys.executable)
    build_ve = os.path.abspath(__file__.replace('build_artifact',
                                                'build_virtualenv'))
    subprocess.check_call((python, build_ve,
                           '-a', opts.app, '--download', '--upload'))
    subprocess.check_call((python, build_ve,
                           '-a', 'deploy', '--download', '--upload'),
                          cwd='deploy')
    shutil.rmtree('deploy/virtualenv')
    os.unlink('deploy/virtualenv.tar.gz')

    env = copy.copy(os.environ)
    env['APPNAME'] = opts.app
    subprocess.check_call('scripts/build.sh', env=env)
    if not opts.skip_tests:
        subprocess.check_call('scripts/test.sh', env=env)
    subprocess.check_call('scripts/dist.sh', env=env)

    artifact = 'dist/%s.tar.gz' % opts.app
    metadata = {
        'deploy_compat': '3',
    }

    deploy_settings = yola.deploy.config.load_settings(opts.config)
    repository = yola.deploy.repository.get_repository(deploy_settings)
    try:
        latest_version = repository.latest_version(opts.app,
                                                   target=opts.target)
    except KeyError:
        latest_version = '0'
    version = str(int(latest_version) + 1)
    with open(artifact) as f:
        repository.put(opts.app, version, f, metadata, target=opts.target)

if __name__ == '__main__':
    main()
