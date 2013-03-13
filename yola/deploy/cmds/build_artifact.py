#!/usr/bin/env python

import argparse
import copy
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


class Builder(object):
    def __init__(self, app, target, version, commit, commit_msg, tag,
                 deploy_settings, repository, build_virtualenvs):
        self.app = app
        self.target = target
        self.version = version
        self.commit = commit
        self.commit_msg = commit_msg
        self.tag = tag
        self.deploy_settings = deploy_settings
        self.repository = repository
        self.build_virtualenvs = build_virtualenvs

    def set_commit_status(self, status, description):
        """Report test status to GitHub"""
        settings = self.deploy_settings.build.github
        if not settings.report:
            return

        subst = {
            'app': self.app,
            'commit': self.commit,
            'fqdn': socket.getfqdn(),
            'version': self.version,
        }
        repo = settings.repo % subst
        subst['repo'] = repo
        url = ('https://api.github.com/repos/%(repo)s/statuses/%(commit)s'
               % subst)
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
            print >> sys.stderr, "Failed to notify GitHub: %s" % e

    def prepare(self):
        raise NotImplemented()

    def build_env(self):
        """Return environment variables to be exported for the build"""
        env = copy.copy(os.environ)
        # Some of the old build scripts depend on APPNAME
        env['APPNAME'] = self.app
        return env

    def build(self, skip_tests=False):
        env = self.build_env()
        subprocess.check_call('scripts/build.sh', env=env)
        if not skip_tests:
            self.set_commit_status('pending', 'Tests Running')
            try:
                subprocess.check_call('scripts/test.sh', env=env)
            except subprocess.CalledProcessError:
                self.set_commit_status('failed', 'Tests did not pass')
                print >> sys.stderr, 'Tests failed'
                sys.exit(1)
            self.set_commit_status('success', 'Tests passed')

        subprocess.check_call('scripts/dist.sh', env=env)

    def upload(self):
        raise NotImplemented()


class BuildCompat1(Builder):
    """The old shell deploy system"""

    def dcs_target(self):
        if self.target == 'master':
            return 'trunk'
        return self.target

    def prepare(self):
        # Legacy config
        self.distname = os.environ.get('DISTNAME', self.app)
        self.dcs = os.environ.get('DEPLOYSERVER',
                self.deploy_settings.build.deploy_content_server)
        self.artifact = os.environ.get('ARTIFACT', './dist/%s.tar.gz'
                                                   % self.app)

    def build_env(self):
        env = super(BuildCompat1, self).build_env()
        env['DISTNAME'] = self.distname
        env['DEPLOYSERVER'] = self.dcs
        env['ARTIFACT'] = self.artifact
        return env

    def upload(self):
        subprocess.check_call(('./scripts/upload.sh',
                               '%s-%s' % (self.app, self.dcs_target()),
                               self.version,
                               self.artifact,
                              ), shell=True, env=self.build_env())


class BuildCompat2(Builder):
    """Call the old scripts in /opt/deploy"""

    def spade_target(self):
        target = ()
        if self.target != 'master':
            target = ('--target', self.target)
        return target

    def prepare(self):
        if self.build_virtualenvs:
            subprocess.check_call(('/opt/deploy/build-virtualenv.py',
                                   '-a', self.app, '--download', '--upload',
                                  ) + self.spade_target())
            subprocess.check_call(('/opt/deploy/build-virtualenv.py',
                                   '-a', 'deploy', '--download', '--upload',
                                  ) + self.spade_target(), cwd='deploy')
            shutil.rmtree('deploy/virtualenv')
            os.unlink('deploy/virtualenv.tar.gz')

    def upload(self):
        artifact = 'dist/%s.tar.gz' % self.app
        metadata = {
            'vcs_tag': self.tag,
            'build_number': self.version,
            'commit_msg': self.commit_msg,
            'commit': self.commit,
            'deploy_compat': '2',
        }

        with open('meta.json', 'w') as f:
            json.dump(metadata, f, indent=4)

        subprocess.check_call(('/opt/deploy/spade.py', self.app, artifact,
                               '-m', 'meta.json',
                              ) + self.spade_target())


class BuildCompat3(Builder):
    def prepare(self):
        python = os.path.abspath(sys.executable)
        build_ve = os.path.abspath(__file__.replace('build_artifact',
                                                    'build_virtualenv'))
        if self.build_virtualenvs:
            subprocess.check_call((python, build_ve,
                                   '-a', self.app, '--target', self.target,
                                   '--download', '--upload'))
            subprocess.check_call((python, build_ve,
                                   '-a', 'deploy', '--target', self.target,
                                   '--download', '--upload'),
                                  cwd='deploy')
            shutil.rmtree('deploy/virtualenv')
            os.unlink('deploy/virtualenv.tar.gz')

    def upload(self):
        artifact = 'dist/%s.tar.gz' % self.app
        metadata = {
            'vcs_tag': self.tag,
            'build_number': self.version,
            'commit_msg': self.commit_msg,
            'commit': self.commit,
            'deploy_compat': '3',
        }

        with open(artifact) as f:
            self.repository.put(self.app, self.version, f, metadata,
                                target=self.target)


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
    parser.add_argument('--no-virtualenvs', action='store_false',
                        dest='build_virtualenvs',
                        help='Ignore building virtualenvs')
    parser.add_argument('-c', '--config', metavar='FILE',
                        default=yola.deploy.config.find_deploy_config(False),
                        help='Location of the Deploy configuration file.')
    opts = parser.parse_args()

    if opts.config is None:
        # Yes, it was a default, but we want to detect its non-existence early
        opts.config = yola.deploy.config.find_deploy_config()

    return opts


def next_version(app, target, repository, deploy_settings):
    """Produce a suitable next version for app, based on existing versions"""
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


def check_output(*args, **kwargs):
    '''
    Backport of subprocess.check_output, with enough features for this module
    '''
    p = subprocess.Popen(stdout=subprocess.PIPE, *args, **kwargs)
    output = p.communicate()[0]
    ret = p.poll()
    if ret:
        raise subprocess.CalledProcessError(ret, *args, output=output)
    return output


def main():
    opts = parse_args()

    compat = 1
    if os.path.exists('deploy/compat'):
        with open('deploy/compat') as f:
            compat = int(f.read().strip())
    try:
        BuilderClass = {
            1: BuildCompat1,
            2: BuildCompat2,
            3: BuildCompat3,
        }[compat]
    except KeyError:
        print >> sys.stderr, 'Only deploy compat >=3 apps are supported'
        sys.exit(1)

    deploy_settings = yola.deploy.config.load_settings(opts.config)
    repository = yola.deploy.repository.get_repository(deploy_settings)

    # Jenkins exports these environment variables
    # but we have some fallbacks
    commit = os.environ.get('GIT_COMMIT')
    if not commit:
        commit = check_output(('git', 'rev-parse', 'HEAD')).strip()
    version = os.environ.get('BUILD_NUMBER')
    if not version:
        version = next_version(opts.app, opts.target, repository,
                               deploy_settings)
    # Other git bits:
    commit_msg = check_output(('git', 'show', '-s', '--format=%s',
                               commit)).strip()
    tags = check_output(('git', 'tag', '--contains', commit))
    tag = None
    for line in tags.splitlines():
        line = line.strip()
        if line.startswith('jenkins-'):
            continue
        tag = line
        break

    builder = BuilderClass(app=opts.app, target=opts.target, version=version,
                           commit=commit, commit_msg=commit_msg, tag=tag,
                           deploy_settings=deploy_settings,
                           repository=repository,
                           build_virtualenvs=opts.build_virtualenvs)
    builder.prepare()
    builder.build(opts.skip_tests)
    builder.upload()


if __name__ == '__main__':
    main()
