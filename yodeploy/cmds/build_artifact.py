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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from yoconfigurator.base import write_config
from yoconfigurator.smush import config_sources, smush_config
import yodeploy.config
import yodeploy.repository


class Builder(object):
    def __init__(self, app, target, version, commit, commit_msg, branch, tag,
                 deploy_settings, repository, build_virtualenvs):
        print_banner('%s %s' % (app, version), border='double')
        self.app = app
        self.target = target
        self.version = version
        self.commit = commit
        self.commit_msg = commit_msg
        self.branch = branch
        self.tag = tag
        self.deploy_settings = deploy_settings
        self.repository = repository
        self.build_virtualenvs = build_virtualenvs

    def set_commit_status(self, status, description):
        """Report test status to GitHub"""
        settings = self.deploy_settings.build.github
        if not settings.report:
            return
        if self.branch in settings.except_branches:
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
        pass

    def build_env(self):
        """Return environment variables to be exported for the build"""
        env = copy.copy(os.environ)
        # Some of the old build scripts depend on APPNAME
        env['APPNAME'] = self.app
        return env

    def build(self, skip_tests=False):
        print_banner('Build')
        env = self.build_env()
        check_call('scripts/build.sh', env=env, abort='Build script failed')
        print_banner('Test')
        if skip_tests:
            print 'Tests skipped'
        else:
            self.set_commit_status('pending', 'Tests Running')
            try:
                check_call('scripts/test.sh', env=env)
            except subprocess.CalledProcessError:
                self.set_commit_status('failure', 'Tests did not pass')
                abort('Tests failed')
            self.set_commit_status('success', 'Tests passed')

        print_banner('Package')
        check_call('scripts/dist.sh', env=env, abort='Dist script failed')

    def upload(self):
        raise NotImplemented()

    def summary(self):
        print_banner('Summary')
        print 'App: %s' % self.app
        print 'Target: %s' % self.target
        print 'Version: %s' % self.version
        print 'Branch: %s' % self.branch
        print 'Commit: %s' % self.commit
        print 'Commit message: %s' % self.commit_msg
        jenkins_tag = ''
        if self.tag:
            print 'Tag: %s' % self.tag
            jenkins_tag = ' (tag: %s)' % self.tag
        print
        print ('Jenkins description: %s:%.8s%s "%s"'
               % (self.target, self.commit, jenkins_tag, self.commit_msg))


class BuildCompat1(Builder):
    """The old shell deploy system"""

    def dcs_target(self):
        if self.deploy_settings.artifacts.environment == 'integration':
            return 'integration'
        if self.target == 'master':
            return 'trunk'
        return self.target

    def prepare(self):
        # Legacy config
        self.distname = os.environ.get('DISTNAME', self.app)
        self.dcs = os.environ.get('DEPLOYSERVER',
                                  self.deploy_settings.build.deploy_content_server)
        self.artifact = os.environ.get('ARTIFACT', './dist/%s.tar.gz'
                                                   % self.distname)
        print 'Environment:'
        print ' DISTNAME=%s' % self.distname
        print ' DEPLOYSERVER=%s' % self.dcs
        print ' ARTIFACT=%s' % self.artifact

    def build_env(self):
        env = super(BuildCompat1, self).build_env()
        env['DISTNAME'] = self.distname
        env['DEPLOYSERVER'] = self.dcs
        env['ARTIFACT'] = self.artifact
        return env

    def upload(self):
        print_banner('Upload')
        check_call(' '.join(('./scripts/upload.sh', '%s-%s' % (self.app,
                                                               self.dcs_target()),
                             self.version, self.artifact)),
                   shell=True, env=self.build_env(), abort='Upload script failed')


class BuildCompat3(Builder):
    compat = 3

    def configure(self):
        build_settings = self.deploy_settings.build
        configs_dirs = [build_settings.configs_dir]
        app_conf_dir = os.path.join('deploy', 'configuration')
        sources = config_sources(self.app, build_settings.environment,
                                 build_settings.cluster,
                                 configs_dirs, app_conf_dir, build=True)
        config = smush_config(sources,
                              initial={'yoconfigurator': {
                                  'app': self.app,
                                  'environment': build_settings.environment,
                             }})
        write_config(config, '.')

    def prepare(self):
        python = os.path.abspath(sys.executable)
        build_ve = os.path.abspath(__file__.replace('build_artifact',
                                                    'build_virtualenv'))
        if self.build_virtualenvs:
            print_banner('Build deploy virtualenv')
            check_call((python, build_ve, '-a', 'deploy',
                        '--target', self.target, '--download', '--upload'),
                       cwd='deploy', abort='build-virtualenv failed')
            shutil.rmtree('deploy/virtualenv')
            os.unlink('deploy/virtualenv.tar.gz')
        if os.path.exists('requirements.txt'):
            print_banner('Build app virtualenv')
            check_call((python, build_ve, '-a', self.app,
                        '--target', self.target, '--download', '--upload'),
                       abort='build-virtualenv failed')
        self.configure()

    def upload(self):
        print_banner('Upload')
        artifact = 'dist/%s.tar.gz' % self.app
        metadata = {
            'build_number': self.version,
            'commit_msg': self.commit_msg,
            'commit': self.commit,
            'deploy_compat': str(self.compat),
        }
        if self.tag:
            metadata['vcs_tag'] = self.tag

        with open(artifact) as f:
            self.repository.put(self.app, self.version, f, metadata,
                                target=self.target)
        print 'Uploaded'


class BuildCompat4(BuildCompat3):
    compat = 4


def parse_args(default_app):
    parser = argparse.ArgumentParser(
        description='Build and upload an artifact',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--app', '-a',
                        default=default_app,
                        help='The application name')
    parser.add_argument('-T', '--skip-tests', action='store_true',
                        help="Don't run tests")
    parser.add_argument('--target', default='master',
                        help='The target to upload to')
    parser.add_argument('--no-virtualenvs', action='store_false',
                        dest='build_virtualenvs',
                        help='Skip building deploy virtualenvs')
    parser.add_argument('--prepare-only', action='store_true',
                        help="Only prepare (e.g. build virtualenvs) don't "
                             "build")
    parser.add_argument('-c', '--config', metavar='FILE',
                        default=yodeploy.config.find_deploy_config(False),
                        help='Location of the Deploy configuration file.')
    opts = parser.parse_args()

    if opts.config is None:
        # Yes, it was a default, but we want to detect its non-existence early
        opts.config = yodeploy.config.find_deploy_config()

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


def check_call(*args, **kwargs):
    '''
    Wrapper around subprocess.check_call, that flushes file file handles first
    Should the call fail, if `abort` is set to a string, we'll abbort with that
    message.
    '''
    sys.stdout.flush()
    sys.stderr.flush()

    abort_msg = kwargs.pop('abort', None)
    try:
        subprocess.check_call(*args, **kwargs)
    except subprocess.CalledProcessError:
        if abort_msg:
            abort(abort_msg)
        else:
            raise


def check_output(*args, **kwargs):
    '''
    Backport of subprocess.check_output, with enough features for this module
    '''
    p = subprocess.Popen(stdout=subprocess.PIPE, *args, **kwargs)
    output = p.communicate()[0]
    ret = p.poll()
    if ret:
        raise subprocess.CalledProcessError(ret, args)
    return output


def print_box(lines, border='light'):
    '''Print lines (a list of unicode strings) inside a pretty box.'''
    styles = {
        'ascii': {
            'ul': '+',
            'ur': '+',
            'dl': '+',
            'dr': '+',
            'h': '-',
            'v': '|',
        },
        'light': {
            'ul': u'\N{BOX DRAWINGS LIGHT UP AND LEFT}',
            'ur': u'\N{BOX DRAWINGS LIGHT UP AND RIGHT}',
            'dl': u'\N{BOX DRAWINGS LIGHT DOWN AND LEFT}',
            'dr': u'\N{BOX DRAWINGS LIGHT DOWN AND RIGHT}',
            'h': u'\N{BOX DRAWINGS LIGHT HORIZONTAL}',
            'v': u'\N{BOX DRAWINGS LIGHT VERTICAL}',
        },
        'heavy': {
            'ul': u'\N{BOX DRAWINGS HEAVY UP AND LEFT}',
            'ur': u'\N{BOX DRAWINGS HEAVY UP AND RIGHT}',
            'dl': u'\N{BOX DRAWINGS HEAVY DOWN AND LEFT}',
            'dr': u'\N{BOX DRAWINGS HEAVY DOWN AND RIGHT}',
            'h': u'\N{BOX DRAWINGS HEAVY HORIZONTAL}',
            'v': u'\N{BOX DRAWINGS HEAVY VERTICAL}',
        },
        'double': {
            'ul': u'\N{BOX DRAWINGS DOUBLE UP AND LEFT}',
            'ur': u'\N{BOX DRAWINGS DOUBLE UP AND RIGHT}',
            'dl': u'\N{BOX DRAWINGS DOUBLE DOWN AND LEFT}',
            'dr': u'\N{BOX DRAWINGS DOUBLE DOWN AND RIGHT}',
            'h': u'\N{BOX DRAWINGS DOUBLE HORIZONTAL}',
            'v': u'\N{BOX DRAWINGS DOUBLE VERTICAL}',
        },
    }
    borders = styles[border]

    width = max(len(line) for line in lines)

    output = [borders['dr'] + borders['h'] * width + borders['dl']]
    for line in lines:
        output.append(borders['v'] + line.ljust(width) + borders['v'])
    output.append(borders['ur'] + borders['h'] * width + borders['ul'])

    print '\n'.join(line.encode('utf-8') for line in output)


def print_banner(message, width=79, position='left', **kwargs):
    '''Print a single-line message in a box'''
    # Ensure there's always space for the border
    assert len(message) <= (width - 4)
    width -= 2

    if position == 'left':
        message = u' ' + message.ljust(width - 1)
    elif position in ('center', 'centre'):
        message = message.center(width)
    elif position == 'right':
        message = message.rjust(width)

    print_box([message], **kwargs)


def abort(message):
    print >> sys.stderr, message
    print_banner('Aborted')
    sys.exit(1)


def main():
    default_app = os.environ.get('JOB_NAME', os.path.basename(os.getcwd()))
    opts = parse_args(default_app)

    compat = 1
    if os.path.exists('deploy/compat'):
        with open('deploy/compat') as f:
            compat = int(f.read().strip())
    print 'Detected build compat level %s' % compat
    try:
        BuilderClass = {
            1: BuildCompat1,
            3: BuildCompat3,
            4: BuildCompat4,
        }[compat]
    except KeyError:
        print >> sys.stderr, ('Only legacy and yodeploy compat >=3 apps '
                              'are supported')
        sys.exit(1)

    deploy_settings = yodeploy.config.load_settings(opts.config)
    repository = yodeploy.repository.get_repository(deploy_settings)

    # Jenkins exports these environment variables
    # but we have some fallbacks
    commit = os.environ.get('GIT_COMMIT')
    if not commit:
        commit = check_output(('git', 'rev-parse', 'HEAD')).strip()

    branch = os.environ.get('GIT_BRANCH')
    if not branch:
        rbranches = check_output(('git', 'branch', '-r', '--contains', 'HEAD'))
        for rbranch in rbranches.splitlines():
            if ' -> ' in rbranch:
                continue
            remote, branch = rbranch.strip().split('/', 1)
            break

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
                           commit=commit, commit_msg=commit_msg, branch=branch,
                           tag=tag, deploy_settings=deploy_settings,
                           repository=repository,
                           build_virtualenvs=opts.build_virtualenvs)
    builder.prepare()
    if not opts.prepare_only:
        builder.build(opts.skip_tests)
        builder.upload()
    builder.summary()


if __name__ == '__main__':
    main()
