import collections
import copy
import datetime
import json
import logging
import os
import shutil
import uuid

import boto

# TODO: Exorcise
from config.deploy import deploy_settings

log = logging.getLogger(__name__)
Version = collections.namedtuple('Version', ['version_id', 'date_uploaded',
                                             'metadata'])


class AttrDict(dict):
    __getattr__ = dict.__getitem__


# TODO: Probably some unused code in here still
class ArtifactVersions(object):
    '''
    The artifact jsonfile keeps information per artifacts.
    It stores a list of Versions
    '''

    def __init__(self, path):
        self.path = path
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
        with open(self.path, 'w') as f:
            json.dump(state, f, indent=2)

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
        if isinstance(date_uploaded, datetime.datetime):
            date_uploaded = date_uploaded.strftime('%Y-%m-%dT%H:%M:%S.000Z')

        if self.get_version(version_id):
            raise Exception('Failed to append %s to ArtifactVersions, '
                            'version already exists' % version_id)
        version = Version(version_id=version_id, date_uploaded=date_uploaded,
                          metadata=meta)
        self._state.versions.append(version)
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

    def __init__(self, app, filename=None, env=None):
        self.app = app
        self.filename = filename or (app + '.tar.gz')
        self.env = env

        if env:
            self._versions = ArtifactVersions(path=os.path.join(
                deploy_settings.paths.state, 'artifacts', self.app,
                self.env, self.filename + '.versions'))
        else:
            self._versions = ArtifactVersions(path=os.path.join(
                deploy_settings.paths.state, 'artifacts', self.app,
                self.filename + '.versions'))


class LocalArtifacts(ArtifactsBase):
    '''Store artifacts on local machine'''

    @property
    def _local_artifact(self):
        '''return the pathname to the file on local store'''
        if self.env:
            return os.path.join(deploy_settings.paths.artifacts, self.app,
                                self.env, self.filename)
        else:
            return os.path.join(deploy_settings.paths.artifacts, self.app,
                                self.filename)

    @property
    def versions(self):
        '''Get versions available for an artifact'''
        return self._versions

    def update_versions(self):
        pass

    def upload(self, target, meta=None):
        '''Upload a file to the artifacts directory'''
        log.info('Uploading %s to artifacts', target)
        # generate a version_id for the local meta data
        version = str(uuid.uuid4()).replace('-', '')
        artifactpath = self._local_artifact + '.' + version

        log.debug('Copying %s to %s', target, artifactpath)
        parentdir = os.path.dirname(artifactpath)
        if not os.path.exists(parentdir):
            os.makedirs(parentdir)
        shutil.copy(target, artifactpath)

        # Update ymlink to the latest version
        if os.path.exists(self._local_artifact):
            os.remove(self._local_artifact)
        os.symlink(os.path.basename(artifactpath), self._local_artifact)

        # Update the version file
        self._versions.add_version(version, datetime.datetime.now(), meta)

    def download(self, target=None, version=None):
        '''Download artificact to target'''
        if not target:
            target = self.filename
        target = os.path.realpath(target)

        artifactpath = self._local_artifact
        # no version specified? get the latest
        if version:
            artifactpath += '.' + version
        if os.path.islink(artifactpath):
            artifactpath = os.path.join(os.path.dirname(artifactpath),
                                        os.readlink(artifactpath))
        # we could set the local artifacts directory to be same as local store,
        # in which case no copying is needed
        if artifactpath != target:
            shutil.copy2(artifactpath, target)


# TODO: Log progress.
class S3Artifacts(ArtifactsBase):
    def __init__(self, app, filename=None, env=None):
        super(S3Artifacts, self).__init__(app, filename, env)

        s3 = boto.connect_s3(deploy_settings.artifacts.access_key,
                             deploy_settings.artifacts.secret_key)
        self._bucket = s3.get_bucket(deploy_settings.artifacts.bucket)

    @property
    def _s3_filename(self):
        # set the s3 prefix(path) to be app/[env]/filename
        if self.env:
            return os.path.join(self.app, self.env, self.filename)
        else:
            return os.path.join(self.app, self.filename)

    @property
    def versions(self):
        return self._versions

    def update_versions(self):
        '''
        Get versions available for an artifact.
        If marker is given, only versions from marker onwards are returned (so
        we don't return all versions all the time). The marker actually works
        from the most recent backwards, so its only useful for paginating, or
        fetching a resultset and not so much for keeping a marker of the latest
        version (unfortunately).

        Returns Key objects
        '''

        log.info('Updating available versions from S3')

        query = {'prefix': self._s3_filename}
        latest = self._versions.latest
        if latest:
            query['key_marker'] = self.filename
            query['version_id_marker'] = latest.version_id

        keys = []
        for k in self._bucket.get_all_versions(**query):
            if isinstance(k, boto.s3.key.Key) and k.name == self._s3_filename:
                # It'll give us our version_id_marker too
                if latest and latest.version_id == k.version_id:
                    break
                # Amazon stores the date differently when querying key directly
                timestamp = k.last_modified
                k = self._bucket.get_key(self._s3_filename,
                                         version_id=k.version_id)
                keys.append((k.version_id, timestamp, k.metadata))

        # s3 returns blocks from newest>oldest
        for key_tuple in reversed(keys):
            self._versions.add_version(*key_tuple)

        if keys:
            log.info('%s new versions available' % len(keys))
        else:
            log.debug('No new versions available')

        return self._versions

    def upload(self, target, meta=None):
        '''Upload a file to the artifacts server'''
        k = boto.s3.key.Key(self._bucket)
        k.key = self._s3_filename
        if meta:
            k.update_metadata(meta)
        k.set_contents_from_filename(target, reduced_redundancy=True)

    def download(self, target=None, version=None):
        '''
        Download artificact from s3://bucket/app/[env]/filename and save to
        target. If the target directory doesnt exist, it is created. The
        version downloaded is returned.
        '''
        if not target:
            target = self.filename
        target = os.path.realpath(target)

        # check we haven't downloaded it already
        if os.path.exists(target):
            log.debug('File already downloaded, skipping fetch')
            return

        k = self._bucket.get_key(self._s3_filename, version_id=version)
        if version == None:
            version = k.version_id
        k.get_contents_to_filename(target, version_id=version)


# a quick factory to return the right class transparently
def artifacts_factory():
    artifacts = None
    if 'provider' in deploy_settings.artifacts:
        if deploy_settings.artifacts.provider == 'local':
            artifacts = LocalArtifacts
        elif deploy_settings.artifacts.provider == 's3':
            artifacts = S3Artifacts
        else:
            raise Exception('Unknown artifacts provider')
    else:
        # default - to account for pre-provider settings - assume s3
        artifacts = S3Artifacts
    return artifacts

Artifacts = artifacts_factory()
