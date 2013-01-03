import errno
import json
import logging
import os
import re
import shutil
from StringIO import StringIO

import boto

log = logging.getLogger(__name__)


def version_sort_key(version):
    '''
    key function for a simple string sort that orders embedded integers
    e.g. c1 > b10 > b2 > b > a
    '''
    parts = re.split(r'(?u)([0-9]+)', version)
    parts[1::2] = [int(part) for part in parts[1::2]]
    return parts


class RepositoryFile(object):
    '''File object wrapper that has a metadata attraibute'''

    def __init__(self, f, metadata):
        self._f = f
        self.metadata = metadata

    def __getattr__(self, name):
        return getattr(self._f, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._f.close()


class Repository(object):
    '''An artifact repository'''

    def __init__(self, store):
        self.store = store

    def get(self, app, version=None, target='master', artifact=None):
        '''
        Return an open file for the requested artifact.
        The metadata will be attached as a 'metadata' attribute.
        '''
        if not artifact:
            artifact = u'%s.tar.gz' % app
        artifact_path = os.path.join(app, target, artifact)
        if not version:
            with self.store.get(os.path.join(artifact_path, 'latest')) as f:
                version = f.read().strip()

        path = os.path.join(artifact_path, unicode(version))
        f, metadata = self.store.get(path, meta=True)
        return RepositoryFile(f, metadata)

    def put(self, app, version, fp, metadata, target='master',
            artifact=None):
        if not artifact:
            artifact = u'%s.tar.gz' % app
        if version == 'latest':
            raise ValueError('Illegal version: %s' % version)
        artifact_path = os.path.join(app, target, artifact)
        path = os.path.join(artifact_path, unicode(version))
        self.store.put(path, fp, metadata)
        latest_path = os.path.join(artifact_path, 'latest')
        self.store.put(latest_path, StringIO(version + '\n'))

    def delete(self, app, version, target='master', artifact=None):
        self.store.delete(app, version, target, artifact)

    def list_apps(self):
        return self.store.list_apps()
        #return sorted(self._list(self.root))

    def list_targets(self, app):
        return self.store.list_targets(app)
        #return sorted(self.list(os.path.join(self.root, app)))

    def list_artifacts(self, app, target='master'):
        return self.store.list_artifacts(app, target)
        #return sorted(self.list(os.path.join(self.root, app, target)))

    def list_versions(self, app, target='master', artifact=None):
        return self.store.list_versions(app, target, artifact)
        #if not artifact:
        #    artifact = u'%s.tar.gz' % app
        #directory = os.path.join(self.root, app, target, artifact)
        #versions = []
        #for version in self._list(directory, files=True, dirs=False):
        #    if version == u'latest' or version.endswith(u'.meta'):
        #        continue
        #    versions.append(version)
        #return sorted(versions, key=version_sort_key)

    def gc(self, max_versions=10):
        '''
        Delete all but the most recent max_versions versions of each artifact
        in the repository
        '''
        for app in self.list_apps():
            for target in self.list_targets(app):
                for artifact in self.list_artifacts(app, target):
                    versions = self.list_versions(app, target, artifact)
                    versions.reverse()
                    for version in versions[max_versions:]:
                        self.delete(app, version, target, artifact)


class LocalRepositoryStore(object):
    '''Store artifacts on local machine'''

    def __init__(self, root):
        if not os.path.isdir(root):
            raise Exception("root directory %s doesn't exist" % root)
        self.root = root

    def get(self, path, meta=False):
        fn = os.path.join(self.root, path)
        meta_fn = fn + '.meta'
        if not os.path.exists(fn) or (meta and not os.path.exists(meta_fn)):
            raise KeyError('No such object')

        if meta:
            with open(meta_fn) as f:
                metadata = json.load(f)
            return open(fn), metadata
        return open(fn)

    def put(self, path, fp, metadata=None):
        '''
        Store an artifact (fp).
        Optionally attach metadata to it.
        '''
        directory = os.path.dirname(os.path.join(self.root, path))
        if not os.path.isdir(directory):
            os.makedirs(directory)

        fn = os.path.join(self.root, path)
        if metadata is not None:
            meta_fn = fn + '.meta'
            with open(meta_fn, 'w') as f:
                json.dump(metadata, f)
        with open(fn, 'w') as f:
            shutil.copyfileobj(fp, f)

    def delete(self, app, version, target='master', artifact=None):
        if not artifact:
            artifact = u'%s.tar.gz' % app
        artifact_dir = os.path.join(self.root, app, target, artifact)
        fn = os.path.join(artifact_dir, unicode(version))
        if not os.path.exists(fn):
            raise ValueError('No such version: %s/%s %s', app, target, version)

        latest_fn = os.path.join(artifact_dir, 'latest')
        with open(latest_fn) as f:
            latest = f.read().strip()
        if latest == version:
            versions = self.list_versions(app, target, artifact)
            try:
                versions.remove(version)
            except ValueError:
                pass
            if versions:
                with open(latest_fn, 'w') as f:
                    f.write(versions[-1] + '\n')
            else:
                os.unlink(latest_fn)

        os.unlink(fn)
        os.unlink(fn + '.meta')

    def _list(self, directory, files=False, dirs=True):
        predicates = [os.path.islink]
        if files:
            predicates.append(os.path.isfile)
        if dirs:
            predicates.append(os.path.isdir)

        try:
            for filename in os.listdir(directory):
                pathname = os.path.join(directory, filename)
                if any(predicate(pathname) for predicate in predicates):
                    yield filename
        except OSError, e:
            if e.errno != errno.ENOENT:
                raise

    def list_apps(self):
        return sorted(self._list(self.root))

    def list_targets(self, app):
        return sorted(self._list(os.path.join(self.root, app)))

    def list_artifacts(self, app, target='master'):
        return sorted(self._list(os.path.join(self.root, app, target)))

    def list_versions(self, app, target='master', artifact=None):
        if not artifact:
            artifact = u'%s.tar.gz' % app
        directory = os.path.join(self.root, app, target, artifact)
        versions = []
        for version in self._list(directory, files=True, dirs=False):
            if version == u'latest' or version.endswith(u'.meta'):
                continue
            versions.append(version)
        return sorted(versions, key=version_sort_key)


class S3Repository(object):
    '''Store artifacts on S3'''

    def __init__(self, bucket, access_key, secret_key):
        s3 = boto.connect_s3(access_key, secret_key)
        self.bucket = s3.get_bucket(bucket)


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
