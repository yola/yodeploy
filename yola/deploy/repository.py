import json
import logging
import os
import re
import shutil

log = logging.getLogger(__name__)


def version_sort_key(version):
    '''
    key function for a simple string sort that orders embedded integers
    e.g. c1 > b10 > b2 > b > a
    '''
    parts = re.split(r'(?u)([0-9]+)', version)
    parts[1::2] = [int(part) for part in parts[1::2]]
    return parts


class LocalRepository(object):
    '''Store artifacts on local machine'''

    def __init__(self, root):
        self._root = root

    def get(self, app, version=None, target='default', artifact=None):
        '''
        Return an open file for the requested artifact.
        '''
        if not artifact:
            artifact = u'%s.tar.gz' % app
        artifact_dir = os.path.join(self._root, app, target, artifact)
        if not version:
            with open(os.path.join(artifact_dir, 'latest')) as f:
                version = f.read().strip()

        fn = os.path.join(artifact_dir, unicode(version))
        meta_fn = fn + '.meta'
        if not os.path.exists(fn) or not os.path.exists(meta_fn):
            raise KeyError('Requested version does not exist')
        with open(meta_fn) as f:
            metadata = json.load(f)
        return open(fn), metadata

    def store(self, app, version, fp, metadata, target='default',
              artifact=None):
        '''
        Store an artifact (fp)
        '''
        if not artifact:
            artifact = u'%s.tar.gz' % app
        artifact_dir = os.path.join(self._root, app, target, artifact)

        fn = os.path.join(artifact_dir, unicode(version))
        meta_fn = fn + '.meta'
        with open(meta_fn, 'w') as f:
            json.dump(meta_fn, metadata)
        with open(fn, 'w') as f:
            shutil.copyfileobj(fp, f)

        with open(os.path.join(artifact_dir, 'latest'), 'w') as f:
            f.write(version + '\n')

    def delete(self, app, version, target='default', artifact=None):
        if not artifact:
            artifact = u'%s.tar.gz' % app
        fn = os.path.join(self._root, app, target, artifact, unicode(version))
        os.unlink(fn)
        os.unlink(fn + '.meta')

    def _list(self, directory):
        for filename in os.listdir(directory):
            pathname = os.path.join(directory, filename)
            if os.path.islink(pathname) or os.path.isdir(pathname):
                yield filename

    def list_apps(self):
        return sorted(self._list(self._root))

    def list_targets(self, app):
        return sorted(self._list(os.path.join(self._root, app)))

    def list_artifacts(self, app, target='default'):
        return sorted(self._list(os.path.join(self._root, app, 'target')))

    def list_versions(self, app, target='default', artifact=None):
        if not artifact:
            artifact = u'%s.tar.gz' % app
        directory = os.path.join(self._root, app, target, artifact)
        return sorted(self._list(directory), key=version_sort_key)

    def gc(self, max_versions=10):
        '''
        Delete all but the most recent max_versions versions of each artifact
        in the repository
        '''
        for app in self.list_apps():
            for target in self.list_targets(app):
                for artifact in self.list_artifacts(app, target):
                    versions = self.list_versions(app, target, artifact)
                    for version in versions[max_versions:]:
                        self.delete(app, version, target, artifact)


def build_repository_factory(deploy_settings):
    '''
    Return a factory that will build the correct Artifacts class for our
    deploy_settings
    '''
    def factory():
        provider = deploy_settings.artifacts.get('provider', 's3')
        if provider == 'local':
            return LocalRepository(deploy_settings.paths.artifacts)
        else:
            raise ValueError("Unknown Artifacts Provider: %s" % provider)
    return factory
