#!/usr/bin/env python
from __future__ import print_function
import argparse
import copy
import json
import os
import shutil
import socket
import subprocess
import sys
from xml.etree import ElementTree

try:
    from urllib.request import Request, urlopen
    from urllib.error import URLError
except ImportError:
    from urllib2 import Request, urlopen, URLError

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from yoconfigurator.base import write_config  # noqa
from yoconfigurator.filter import filter_config  # noqa
from yoconfigurator.smush import config_sources, smush_config  # noqa
import yodeploy.config  # noqa
import yodeploy.repository  # noqa
from yodeploy.unicode_stdout import ensure_unicode_compatible


class Builder(object):
    def __init__(self, app, target, version, commit, commit_msg, branch, tag,
                 deploy_settings, deploy_settings_file, repository,
                 build_virtualenvs, upload_virtualenvs):
        print_banner('%s %s' % (app, version), border='double')
        self.app = app
        self.target = target
        self.version = version
        self.commit = commit
        self.commit_msg = commit_msg
        self.branch = branch
        self.tag = tag
        self.deploy_settings = deploy_settings
        self.deploy_settings_file = deploy_settings_file
        self.repository = repository
        self.build_virtualenvs = build_virtualenvs
        self.upload_virtualenvs = upload_virtualenvs

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
        target_url = os.environ.get('BUILD_URL', settings.url % subst)

        build_environment = self.deploy_settings.artifacts.environment
        build_label = os.environ.get('JENKINS_SLAVE', None)

        context = 'yodeploy/%s' % build_environment
        if build_label:
            context += '/%s' % build_label

        data = {
            'state': status,
            'target_url': target_url,
            'description': description,
            'context': context,
        }
        req = Request(
            url=url,
            data=json.dumps(data),
            headers={
                'Authorization': 'token %s' % settings.oauth_token,
            })
        try:
            urlopen(req)
        except URLError as e:
            print('Failed to notify GitHub: %s' % e, file=sys.stderr)

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

        # public configuration
        public_filter_pathname = os.path.join(app_conf_dir, 'public-data.py')
        public_config = filter_config(config, public_filter_pathname)
        if public_config:
            write_config(public_config, '.', 'configuration_public.json')

    def prepare(self):
        python = os.path.abspath(sys.executable)
        build_ve = os.path.abspath(__file__.replace('build_artifact',
                                                    'build_virtualenv'))
        build_deploy_virtualenv = [python, build_ve, '-a', 'deploy',
                                   '--target', self.target, '--download',
                                   '--config', self.deploy_settings_file,
                                   '--compat=%i' % self.compat]
        build_app_virtualenv = [python, build_ve, '-a', self.app,
                                '--target', self.target, '--download',
                                '--config', self.deploy_settings_file]
        if self.upload_virtualenvs:
            build_deploy_virtualenv.append('--upload')
            build_app_virtualenv.append('--upload')

        if self.build_virtualenvs:
            print_banner('Build deploy virtualenv')
            check_call(build_deploy_virtualenv, cwd='deploy',
                       abort='build-virtualenv failed')
            shutil.rmtree('deploy/virtualenv')
            os.unlink('deploy/virtualenv.tar.gz')
        if os.path.exists('requirements.txt'):
            print_banner('Build app virtualenv')
            check_call(build_app_virtualenv, abort='build-virtualenv failed')
        self.configure()

    def build_env(self):
        """Return environment variables to be exported for the build"""
        env = copy.copy(os.environ)
        # Some of the old build scripts depend on APPNAME
        env['APPNAME'] = self.app
        return env

    def build(self):
        print_banner('Build')
        env = self.build_env()
        check_call('scripts/build.sh', env=env, abort='Build script failed')
        print_banner('Package')
        check_call('scripts/dist.sh', env=env, abort='Dist script failed')

    def test(self):
        print_banner('Test')
        env = self.build_env()
        self.set_commit_status('pending', 'Tests Running')
        failed = False

        try:
            check_call('scripts/test.sh', env=env)
        except subprocess.CalledProcessError:
            failed = True

        msg = 'Tests %s' % ('failed' if failed else 'passed')
        results = {'tests': 0, 'failures': 0, 'errors': 0, 'skip': 0}

        for report_file in ('xunit', 'xunit-integration'):
            report_path = 'test_build/reports/%s.xml' % report_file
            if os.path.isfile(report_path):
                test_tree = ElementTree.parse(report_path)
                test_suite = test_tree.find('testsuite') or test_tree.getroot()
                for (k, v) in test_suite.attrib.items():
                    if k in results:
                        results[k] += int(v)

        if any(results.values()):
            msg = ('Ran %(tests)s tests: %(failures)s failures, '
                   '%(errors)s errors, %(skip)s skipped') % results

        # If the test script is intentionally ignoring test failures, don't
        # fail the build
        commit_status = failed or bool(results['failures'])

        self.set_commit_status(
            'failure' if commit_status else 'success', msg)

        if failed:
            abort(msg)

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

        with open(artifact, 'rb') as f:
            self.repository.put(self.app, self.version, f, metadata,
                                target=self.target)
        print('Uploaded')

    def summary(self):
        print_banner('Summary')
        print('App: %s' % self.app)
        print('Target: %s' % self.target)
        print('Version: %s' % self.version)
        print('Branch: %s' % self.branch)
        print('Commit: %s' % self.commit)
        print('Commit message: %s' % self.commit_msg)
        jenkins_tag = ''
        if self.tag:
            print('Tag: %s' % self.tag)
            jenkins_tag = ' (tag: %s)' % self.tag
        print()
        print('Jenkins description: %s:%.8s%s "%s"' % (
            self.branch.replace('origin/', ''), self.commit, jenkins_tag,
            self.commit_msg))


class BuildCompat4(Builder):
    compat = 4


class BuildCompat5(Builder):
    compat = 5


def parse_args(default_app):
    parser = argparse.ArgumentParser(
        description='Build and upload an artifact',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--app', '-a',
                        default=default_app,
                        help='The application name')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-T', '--skip-tests', action='store_true',
                       help="Don't run tests")
    group.add_argument('--test-only', action='store_true',
                       help="Only test (e.g. build virtualenv and run "
                            "test.sh) don't build/upload")
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


def print_box(lines, border='light'):
    '''Print lines (a list of unicode strings) inside a pretty box.'''
    styles = {
        'ascii': {
            'ul': u'+',
            'ur': u'+',
            'dl': u'+',
            'dr': u'+',
            'h': u'-',
            'v': u'|',
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

    print(*output, sep='\n')


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
    print(message, file=sys.stderr)
    print_banner('Aborted')
    sys.exit(1)


class GitHelper(object):

    """Get and format info from the local git repo.

    Use the environment variables Jenkins exports.
    Fallback to calling out to git.
    """

    @property
    def commit(self):
        commit = os.environ.get('GIT_COMMIT')
        if not commit:
            commit = subprocess.check_output(
                ('git', 'rev-parse', 'HEAD'), universal_newlines=True)
            commit = commit.strip()
        return commit

    @property
    def branch(self):
        branch = os.environ.get('GIT_BRANCH')
        if branch:
            return branch
        git_branch = ('git', 'branch', '-r', '--contains', 'HEAD')
        rbranches = subprocess.check_output(
            git_branch, universal_newlines=True)

        for rbranch in rbranches.splitlines():
            if ' -> ' in rbranch:
                continue
            remote, branch = rbranch.strip().split('/', 1)
            break
        return branch

    @property
    def commit_msg(self):
        git_show = ('git', 'show', '-s', '--format=%s', self.commit)
        # using universal_newlines below would introduce a string type
        # inconsitency between python 2/3, so we deliberately don't use it
        # so that check_output always returns a byte string here.
        msg = subprocess.check_output(git_show).strip().decode('utf-8')

        # amazon gets unhappy when you attach non-ascii meta, so we convert
        # it to an ascii string causing us to drop all unicode characters
        # (they become ?), but then we change the string back to a unicode
        # string so that it's json.dump friendly in python 3.
        msg = msg.encode('ascii', 'replace').decode('ascii')
        return msg

    @property
    def tag(self):
        tags = subprocess.check_output(
            ('git', 'tag', '--contains', self.commit), universal_newlines=True)

        tag = None
        for line in tags.splitlines():
            line = line.strip()
            if line.startswith('jenkins-'):
                continue
            tag = line
            break
        return tag


def main():
    ensure_unicode_compatible()

    default_app = os.environ.get('JOB_NAME', os.path.basename(os.getcwd()))
    opts = parse_args(default_app)

    compat = 1
    if os.path.exists('deploy/compat'):
        with open('deploy/compat') as f:
            compat = int(f.read().strip())
    print('Detected build compat level %s' % compat)
    try:
        BuilderClass = {
            4: BuildCompat4,
            5: BuildCompat5,
        }[compat]
    except KeyError:
        print('Only legacy and yodeploy compat >=4 apps are supported',
              file=sys.stderr)
        sys.exit(1)

    deploy_settings = yodeploy.config.load_settings(opts.config)
    repository = yodeploy.repository.get_repository(deploy_settings)

    git = GitHelper()
    commit = git.commit
    branch = git.branch
    commit_msg = git.commit_msg
    tag = git.tag

    version = os.environ.get('BUILD_NUMBER')
    if not version:
        version = next_version(opts.app, opts.target, repository,
                               deploy_settings)

    upload_virtualenvs = not opts.test_only

    builder = BuilderClass(app=opts.app, target=opts.target, version=version,
                           commit=commit, commit_msg=commit_msg, branch=branch,
                           tag=tag, deploy_settings=deploy_settings,
                           deploy_settings_file=opts.config,
                           repository=repository,
                           build_virtualenvs=opts.build_virtualenvs,
                           upload_virtualenvs=upload_virtualenvs)
    builder.prepare()
    if not opts.prepare_only:
        if not opts.test_only:
            builder.build()
        if not opts.skip_tests:
            builder.test()
        if not opts.test_only:
            builder.upload()
    builder.summary()


if __name__ == '__main__':
    main()
