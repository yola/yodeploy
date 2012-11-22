import collections
import copy
import datetime
import errno
import json
import logging
import os
import shutil
import uuid

import boto

log = logging.getLogger(__name__)
Version = collections.namedtuple('Version', ['version_id', 'date_uploaded',
                                             'metadata'])


class AttrDict(dict):
    __getattr__ = dict.__getitem__


class ArtifactVersions(object):
    '''
    The artifact jsonfile keeps information per artifacts.
    It stores a list of Versions
    '''

    def __init__(self, path, cache=False):
        '''
        path:  Path to the state file
        cache: Set True if durability is not important. Allows save() to fail
        '''
        self.path = path
        self._is_cache = cache
        self._state = AttrDict()
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            self._state['versions'] = []
            return
        with open(self.path, 'r') as f:
            self._state = AttrDict(json.load(f))
        self._state['versions'] = [
                Version(**version)
                for version in self._state.get('versions', [])]

    def save(self):
        parentdir = os.path.dirname(self.path)
        if not os.path.exists(parentdir):
            os.makedirs(parentdir)
        state = copy.copy(self._state)
        state['versions'] = [version._asdict() for version in self.versions]
        try:
            with open(self.path, 'w') as f:
                json.dump(state, f, indent=2)
        except IOError, e:
            if self._is_cache and e.errno == errno.EACCES:
                log.warn('Unable to store artifact state. '
                         'Permission denied writing %s', self.path)
            else:
                raise

    @property
    def versions(self):
        return self._state.versions

    def get_version(self, version_id):
        '''Get version info by version_id'''
        for v in self.versions:
            if v.version_id == version_id:
                return v
        return None

    @property
    def latest(self):
        '''Return latest versions'''
        if self.versions:
            return self.versions[-1]
        return None

    def add_version(self, version_id, date_uploaded, meta):
        '''Add a version to known versions'''
        assert version_id is not None
        if isinstance(date_uploaded, datetime.datetime):
            date_uploaded = date_uploaded.strftime('%Y-%m-%dT%H:%M:%S.000Z')

        if self.get_version(version_id):
            raise ValueError('Failed to append %s to ArtifactVersions, '
                             'version already exists' % version_id)
        version = Version(version_id=version_id, date_uploaded=date_uploaded,
                          metadata=meta)
        self._state.versions.append(version)
        self.save()

    def clear(self):
        '''Clear our version cache (e.g. if we change artifact store)'''
        self._state['versions'] = []
        self.save()

    def distance(self, from_version, to_version=None):
        '''
        Calculate distance between two versions
        If to_version not given, use latest
        '''
        if not to_version:
            to_version = self.latest.version_id

        start_idx = end_idx = None
        for i, v in enumerate(self.versions):
            if v.version_id == from_version:
                start_idx = i
            if v.version_id == to_version:
                end_idx = i

        if start_idx is not None and end_idx is not None:
            return (end_idx - start_idx)
        else:
            return None


class ArtifactsBase(object):
    '''
    Basic Abstract class for Different Artifacts handler to implement
    '''

    _state_is_cache = False

    def __init__(self, app, target, state_dir, filename=None):
        self.app = app
        self.filename = filename or (app + '.tar.gz')
        self.target = target

        if target:
            self._versions = ArtifactVersions(path=os.path.join(
                state_dir, 'artifacts', self.app, self.target,
                self.filename + '.versions'), cache=self._state_is_cache)
        else:
            self._versions = ArtifactVersions(path=os.path.join(
                state_dir, 'artifacts', self.app,
                self.filename + '.versions'), cache=self._state_is_cache)

    @property
    def versions(self):
        '''Get versions available for an artifact'''
        return self._versions

    def update_versions(self):
        pass


class LocalArtifacts(ArtifactsBase):
    '''Store artifacts on local machine'''

    def __init__(self, app, target, state_dir, artifact_dir, filename=None):
        super(LocalArtifacts, self).__init__(app, target, state_dir, filename)
        self._artifact_dir = artifact_dir

    @property
    def _local_artifact(self):
        '''return the pathname to the file on local store'''
        if self.target:
            return os.path.join(self._artifact_dir, self.app, self.target,
                                self.filename)
        else:
            return os.path.join(self._artifact_dir, self.app, self.filename)

    def upload(self, source, meta=None):
        '''Upload a file to the artifacts directory'''
        log.info('Uploading %s to artifacts', source)
        # generate a version_id for the local meta data
        version = str(uuid.uuid4()).replace('-', '')
        artifactpath = self._local_artifact + '.' + version

        log.debug('Copying %s to %s', source, artifactpath)
        parentdir = os.path.dirname(artifactpath)
        if not os.path.exists(parentdir):
            os.makedirs(parentdir)
        shutil.copy(source, artifactpath)

        # Update the version file
        self._versions.add_version(version, datetime.datetime.now(), meta)

        # Update symlink to the latest version
        if os.path.exists(self._local_artifact):
            os.remove(self._local_artifact)
        os.symlink(os.path.basename(artifactpath), self._local_artifact)

    def download(self, dest=None, version=None):
        '''Download artificact to dest'''
        if not dest:
            dest = self.filename
        dest = os.path.realpath(dest)

        artifactpath = self._local_artifact
        # no version specified? get the latest
        if version:
            artifactpath += '.' + version
        if not os.path.exists(artifactpath):
            raise Exception("File not present in local artifact store.")
        if os.path.islink(artifactpath):
            artifactpath = os.path.join(os.path.dirname(artifactpath),
                                        os.readlink(artifactpath))
        # we could set the local artifacts directory to be same as local store,
        # in which case no copying is needed
        if artifactpath != dest:
            shutil.copy2(artifactpath, dest)

    def list(self):
        directory = os.path.join(self._artifact_dir, self.app)
        if self.target:
            directory = os.path.join(directory, self.target)
        if not os.path.isdir(directory):
            return []
        listing = []
        for filename in os.listdir(directory):
            pathname = os.path.join(directory, filename)
            if os.path.islink(pathname):
                listing.append(filename)
            if os.path.isdir(pathname):
                listing.append('%s/' % filename)
        listing.sort()
        return listing


# TODO: Log progress.
class S3Artifacts(ArtifactsBase):
    _state_is_cache = True

    def __init__(self, app, target, state_dir, bucket, access_key, secret_key,
                 filename=None):
        super(S3Artifacts, self).__init__(app, target, state_dir, filename)
        s3 = boto.connect_s3(access_key, secret_key)
        self._bucket = s3.get_bucket(bucket)
        if self._bucket.get_versioning_status().get('Versioning') != 'Enabled':
            raise ValueError('S3 bucket "%s" does not have versioning enabled'
                             % bucket)

    @property
    def _s3_filename(self):
        # set the s3 prefix(path) to be app/[target]/filename
        if self.target:
            return os.path.join(self.app, self.target, self.filename)
        else:
            return os.path.join(self.app, self.filename)

    def update_versions(self):
        '''
        Get versions available for an artifact.

        Returns Key objects
        '''

        log.info('Updating available versions from S3')

        latest = self._versions.latest

        keys = []
        for k in self._bucket.list_versions(prefix=self._s3_filename):
            if not isinstance(k, boto.s3.key.Key):
                continue
            if k.name != self._s3_filename:
                continue
            # Stop when we get to a version we already know about
            if latest and latest.version_id == k.version_id:
                break
            # Amazon stores the date differently when querying key directly
            timestamp = k.last_modified
            k = self._bucket.get_key(self._s3_filename,
                                     version_id=k.version_id)
            keys.append((k.version_id, timestamp, k.metadata))
        else:
            if latest:
                log.warn('Our latest version_id is not present in the '
                         'repository. Dropping local version cache')
                self._versions.clear()

        # s3 returns blocks from newest>oldest
        for key_tuple in reversed(keys):
            self._versions.add_version(*key_tuple)

        if keys:
            log.info('%s new versions available' % len(keys))
        else:
            log.debug('No new versions available')

        return self._versions

    def upload(self, source, meta=None):
        '''Upload a file to the artifacts server'''
        k = boto.s3.key.Key(self._bucket)
        k.key = self._s3_filename
        if meta:
            k.update_metadata(meta)
        k.set_contents_from_filename(source, reduced_redundancy=True)

    def download(self, dest=None, version=None):
        '''
        Download artificact from s3://bucket/app/[target]/filename and save to
        dest. If the target directory doesnt exist, it is created. The
        version downloaded is returned.
        '''
        if not dest:
            dest = self.filename
        dest = os.path.realpath(dest)

        k = self._bucket.get_key(self._s3_filename, version_id=version)
        if version is None:
            version = k.version_id
        k.get_contents_to_filename(dest, version_id=version)

    def list(self):
        prefix = '%s/' % self.app
        if self.target:
            prefix += '%s/' % self.target
        return [k.name
                for k in self._bucket.list(prefix=prefix, delimiter='/')]


def build_artifacts_factory(app, target, deploy_settings):
    '''
    Return a factory that will build the correct Artifacts class for our
    deploy_settings
    '''
    def factory(filename=None, app=app):
        provider = deploy_settings.artifacts.get('provider', 's3')
        if provider == 'local':
            return LocalArtifacts(app, target, deploy_settings.paths.state,
                                  deploy_settings.paths.artifacts, filename)
        elif provider == 's3':
            return S3Artifacts(app, target, deploy_settings.paths.state,
                               deploy_settings.artifacts.bucket,
                               deploy_settings.artifacts.access_key,
                               deploy_settings.artifacts.secret_key, filename)
        else:
            raise ValueError("Unknown Artifacts Provider: %s" % provider)
    return factory
