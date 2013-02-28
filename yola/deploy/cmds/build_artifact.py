#!/usr/bin/env python

import argparse
import copy
import functools
import json
import os
import shutil
import socket
import subprocess
import sys
import urllib2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

import yola.deploy.config
import yola.deploy.repository


def parse_args():
    parser = argparse.ArgumentParser(
            description='Build and upload an artifact',
            formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--app', '-a',
                        default=os.path.basename(os.getcwd()),
                        help='The application name')
    parser.add_argument('-T', '--skip-tests', action='store_true',
                          help="Don't run tests")
    parser.add_argument('--target', default='master',
                          help='The target to upload to')
    parser.add_argument('-c', '--config', metavar='FILE',
                        default=yola.deploy.config.find_deploy_config(False),
                        help='Location of the Deploy configuration file.')
    opts = parser.parse_args()

    if opts.config is None:
        # Yes, it was a default, but we want to detect its non-existence early
        opts.config = yola.deploy.config.find_deploy_config()

    return opts


def set_commit_status(status, description, app, commit, version,
                      deploy_settings):
    """Report test status to GitHub"""
    settings = deploy_settings.build.github
    if not settings.report:
        return

    subst = {
        'app': app,
        'commit': commit,
        'fqdn': socket.getfqdn(),
        'version': version,
    }
    repo = settings.repo % subst
    subst['repo'] = repo
    url = 'https://api.github.com/repos/%(repo)s/statuses/%(commit)s' % subst
    data = {
        'state': status,
        'target_url': settings.url % subst,
        'description': description,
    }
    req = urllib2.Request(
            url=url,
            data=json.dumps(data),
            headers={
                'Authorization': 'token %s' % settings.oauth_token,
            })
    try:
        urllib2.urlopen(req)
    except urllib2.URLError, e:
        print >> sys.stderr, "Failed to notify GitHub: %s" % e.reason


def next_version(app, target, repository, deploy_settings):
    """Produce a suitable next verison for app, based on existing verisons"""
    try:
        latest_version = repository.latest_version(app, target=target)
    except KeyError:
        if target != 'master':
            return next_version(app, 'master', repository, deploy_settings)
        return '0'

    # 1 -> 1.1, 1.1 -> 1.2
    version = latest_version.split('.')
    if len(version) == 1:
        version.append('1')
    else:
        version[-1] = str(int(version[-1]) + 1)
    return '.'.join(version)


def main():
    opts = parse_args()

    with open('deploy/compat') as f:
        if f.read().strip() != '3':
            print >> sys.stderr, 'Only deploy compat 3 apps are supported'
            sys.exit(1)

    deploy_settings = yola.deploy.config.load_settings(opts.config)
    repository = yola.deploy.repository.get_repository(deploy_settings)

    # Jenkins exports these environment variables
    # but we have some fallbacks
    commit = os.environ.get('GIT_COMMIT')
    if not commit:
        commit = subprocess.check_output(('git', 'rev-parse', 'HEAD')).strip()
    version = os.environ.get('BUILD_NUMBER')
    if not version:
        version = next_version(opts.app, opts.target, repository,
                               deploy_settings)

    set_commit_status_p = functools.partial(set_commit_status, app=opts.app,
                                            commit=commit, version=version,
                                            deploy_settings=deploy_settings)

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
    # Some of the old build scripts depend on APPNAME
    env['APPNAME'] = opts.app
    subprocess.check_call('scripts/build.sh', env=env)
    if not opts.skip_tests:
        set_commit_status_p('pending', 'Tests Running')
        try:
            subprocess.check_call('scripts/test.sh', env=env)
        except subprocess.CalledProcessError:
            set_commit_status_p('failed', 'Tests did not pass')
            print >> sys.stderr, 'Tests failed'
            sys.exit(1)
        set_commit_status_p('success', 'Tests passed')

    subprocess.check_call('scripts/dist.sh', env=env)

    artifact = 'dist/%s.tar.gz' % opts.app
    metadata = {
        'deploy_compat': '3',
    }

    with open(artifact) as f:
        repository.put(opts.app, version, f, metadata, target=opts.target)

if __name__ == '__main__':
    main()
