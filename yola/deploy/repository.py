import errno
import json
import logging
import os
import re
import shutil
from StringIO import StringIO

import boto

log = logging.getLogger(__name__)
STORES = {}


def version_sort_key(version):
    '''
    key function for a simple string sort that orders embedded integers
    e.g. c1 > b10 > b2 > b > a
    '''
    parts = re.split(r'(?u)([0-9]+)', version)
    parts[1::2] = [int(part) for part in parts[1::2]]
    return parts


def get_repository(deploy_settings):
    '''Create the Repository specified in deploy_settings'''
    store = deploy_settings.artifacts.store
    StoreClass = STORES[store]
    store_settings = deploy_settings.artifacts.store_settings[store]
    return Repository(StoreClass(**store_settings))


def _register_store(name):
    '''Register a store class in STORES'''
    def wrapped_register_store(class_):
        STORES[name] = class_
        return class_

    return wrapped_register_store


class RepositoryFile(object):
    '''File object wrapper that has a metadata attraibute'''

    def __init__(self, f, metadata=None):
        self._f = f
        if metadata is not None:
            self.metadata = metadata

    def __getattr__(self, name):
        return getattr(self._f, name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._f.close()


@_register_store('local')
class LocalRepositoryStore(object):
    '''Store artifacts on local machine'''

    def __init__(self, directory):
        if not os.path.isdir(directory):
            raise Exception("root directory %s doesn't exist" % directory)
        self.root = directory

    def get(self, path, metadata=False):
        '''
        Retrieve a file.
        If metadata is True, metadata will be returned as well, in a tuple.
        '''
        fn = os.path.join(self.root, path)
        if not os.path.exists(fn):
            raise KeyError('No such object: %s' % path)

        if metadata:
            metadata = self.get_metadata(path)
            return open(fn), metadata
        return open(fn)

    def get_metadata(self, path):
        '''
        Retrieve a file's metadata
        '''
        fn = os.path.join(self.root, path)
        meta_fn = fn + '.meta'
        if not os.path.exists(fn):
            raise KeyError('No such object: %s' % path)

        if not os.path.exists(meta_fn):
            return {}

        with open(meta_fn) as f:
            return json.load(f)

    def put(self, path, fp, metadata=None):
        '''
        Store a file (fp).
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

    def delete(self, path, metadata=False):
        '''
        Delete a file.
        If metadata is True, this file has metadata that should be removed too
        '''
        fn = os.path.join(self.root, path)
        try:
            os.unlink(fn)
        except OSError, e:
            if e.errno == errno.ENOENT:
                raise KeyError(e)
            raise
        if metadata:
            try:
                os.unlink(fn + '.meta')
            except OSError, e:
                if e.errno != errno.ENOENT:
                    raise

    def list(self, path=None, files=False, dirs=True):
        '''
        List the contents of path.
        Files will be listed when files is True.
        Directories will be listed when dirs is True.
        '''
        if path:
            directory = os.path.join(self.root, path)
        else:
            directory = self.root
        predicates = []
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


@_register_store('s3')
class S3RepositoryStore(object):
    '''Store artifacts on S3'''

    def __init__(self, bucket, access_key, secret_key, reduced_redundancy,
                 encrypted):
        s3 = boto.connect_s3(access_key, secret_key)
        self.bucket = s3.get_bucket(bucket)
        self.reduced_redundancy = reduced_redundancy
        self.encrypted = encrypted

    def get(self, path, metadata=False):
        '''
        Retrieve a file.
        If metadata is True, metadata will be returned as well, in a tuple.
        '''
        k = self.bucket.get_key(path)
        if k is None:
            raise KeyError('No such object: %s' % path)
        k.open()
        f = RepositoryFile(k.resp)
        if metadata:
            return f, k.metadata
        return f

    def get_metadata(self, path):
        '''
        Retrieve a file's metadata.
        '''
        k = self.bucket.get_key(path)
        if k is None:
            raise KeyError('No such object: %s' % path)
        return k.metadata

    def put(self, path, fp, metadata=None):
        '''
        Store a file (fp).
        Optionally attach metadata to it.
        '''
        k = self.bucket.new_key(path)
        if metadata:
            k.update_metadata(metadata)
        k.set_contents_from_file(fp,
                reduced_redundancy=self.reduced_redundancy,
                encrypt_key=self.encrypted)

    def delete(self, path, metadata=False):
        '''
        Delete a file.
        If metadata is True, this file has metadata that should be removed too
        '''
        k = self.bucket.get_key(path)
        k.delete()

    def list(self, path=None, files=False, dirs=True):
        '''
        List the contents of path.
        Files will be listed when files is True.
        Directories will be listed when dirs is True.
        '''
        if not path:
            path = ''
        accepted_classes = []
        if files:
            accepted_classes.append(boto.s3.key.Key)
        if dirs:
            accepted_classes.append(boto.s3.prefix.Prefix)

        for k in self.bucket.list(prefix=path, delimiter='/'):
            if any(isinstance(k, class_) for class_ in accepted_classes):
                yield k.name


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
        f, metadata = self.store.get(path, metadata=True)
        return RepositoryFile(f, metadata)

    def latest_version(self, app, target='master', artifact=None):
        if not artifact:
            artifact = u'%s.tar.gz' % app
        artifact_path = os.path.join(app, target, artifact)
        with self.store.get(os.path.join(artifact_path, 'latest')) as f:
            return f.read().strip()

    def get_metadata(self, app, version=None, target='master', artifact=None):
        '''
        Return just the metadata for the requested artifact.
        '''
        if not artifact:
            artifact = u'%s.tar.gz' % app
        artifact_path = os.path.join(app, target, artifact)
        if not version:
            with self.store.get(os.path.join(artifact_path, 'latest')) as f:
                version = f.read().strip()

        path = os.path.join(artifact_path, unicode(version))
        return self.store.get_metadata(path)

    def put(self, app, version, fp, metadata, target='master',
            artifact=None):
        '''
        Store an object (fp) in the repository.
        '''
        if not artifact:
            artifact = u'%s.tar.gz' % app
        if version == 'latest' or version.endswith('.meta'):
            raise ValueError('Illegal version: %s' % version)
        artifact_path = os.path.join(app, target, artifact)
        path = os.path.join(artifact_path, unicode(version))
        self.store.put(path, fp, metadata)
        latest_path = os.path.join(artifact_path, 'latest')
        self.store.put(latest_path, StringIO(version + '\n'))

    def delete(self, app, version, target='master', artifact=None):
        '''
        Delete an object from the repository.
        '''
        if not artifact:
            artifact = u'%s.tar.gz' % app
        artifact_path = os.path.join(app, target, artifact)

        versions = self.list_versions(app, target, artifact)
        if version and version not in versions:
            raise ValueError('Non-existent version: %s', version)
        elif not version and not versions:
            raise ValueError('No versions present in the repository')

        latest_path = os.path.join(artifact_path, 'latest')
        latest = versions[-1]
        if latest == version:
            try:
                versions.remove(version)
            except ValueError:
                pass
            if versions:
                self.store.put(latest_path, StringIO(versions[-1] + '\n'))
            else:
                self.store.delete(latest_path)

        path = os.path.join(artifact_path, unicode(version))
        self.store.delete(path, metadata=True)

    def list_apps(self):
        return sorted(self.store.list())

    def list_targets(self, app):
        return sorted(self.store.list(app))

    def list_artifacts(self, app, target='master'):
        return sorted(self.store.list(os.path.join(app, target)))

    def list_versions(self, app, target='master', artifact=None):
        if not artifact:
            artifact = u'%s.tar.gz' % app
        path = os.path.join(app, target, artifact)
        versions = []
        for version in self.store.list(path, files=True, dirs=False):
            if version == u'latest' or version.endswith(u'.meta'):
                continue
            versions.append(version)
        return sorted(versions, key=version_sort_key)

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
