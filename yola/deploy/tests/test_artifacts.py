import json
import os
import tarfile

from ..artifacts import ArtifactVersions, LocalArtifacts
from . import TmpDirTestCase

TEST_JSON = """
{
  "versions": [
    {
      "version_id": "1234567890abcdef1234567890abcdef",
      "date_uploaded": "2012-01-01T00:00:00.000Z",
      "metadata": {
        "deploy_compat": "2",
        "commit_msg": "Hello World",
        "build_number": "1",
        "vcs_tag": ""
      }
    },
    {
      "version_id": "000000000dead00000beef0000000000",
      "date_uploaded": "2012-01-01T08:00:00.000Z",
      "metadata": {
        "deploy_compat": "2",
        "commit_msg": "Hello Again",
        "build_number": "3",
        "vcs_tag": ""
      }
    }
  ]
}
"""
TEST_VERSIONS = json.loads(TEST_JSON)


class TestArtifactiVersions(TmpDirTestCase):
    @property
    def _test_fn(self):
        return self.tmppath('test.json')

    def _write_test_json(self):
        with open(self._test_fn, 'w') as f:
            f.write(TEST_JSON)

    def test_load(self):
        self._write_test_json()
        av = ArtifactVersions(self._test_fn)
        self.assertEqual(len(av.versions), 2)

    def test_save(self):
        av = ArtifactVersions(self._test_fn)
        for version in TEST_VERSIONS['versions']:
            av.add_version(version['version_id'], version['date_uploaded'],
                           version['metadata'])
        av.save()
        with open(self._test_fn, 'r') as f:
            self.assertEqual(json.load(f), TEST_VERSIONS)

    def test_add_existing(self):
        self._write_test_json()
        av = ArtifactVersions(self._test_fn)
        v = TEST_VERSIONS['versions'][0]
        self.assertRaises(Exception, av.add_version, v['version_id'],
                                                     v['date_uploaded'],
                                                     v['metadata'])

    def test_get_version(self):
        self._write_test_json()
        av = ArtifactVersions(self._test_fn)
        self.assertEqual(av.get_version('1234567890abcdef1234567890abcdef')
                         .metadata['commit_msg'],
                         'Hello World')

    def test_latest(self):
        self._write_test_json()
        av = ArtifactVersions(self._test_fn)
        self.assertEqual(av.latest, av.versions[-1])

    def test_no_latest(self):
        av = ArtifactVersions(self._test_fn)
        self.assertTrue(av.latest is None)

    def test_distance(self):
        self._write_test_json()
        av = ArtifactVersions(self._test_fn)
        self.assertEqual(av.distance('1234567890abcdef1234567890abcdef'),
                         1)
        self.assertEqual(av.distance('1234567890abcdef1234567890abcdef',
                                     av.latest.version_id),
                         1)

    def test_distance_unknown(self):
        av = ArtifactVersions(self._test_fn)
        self.assertTrue(av.distance('abc', 'def') is None)


class TestLocalArtifacts(TmpDirTestCase):
    def setUp(self):
        super(TestLocalArtifacts, self).setUp()
        os.mkdir(self.tmppath('state'))
        os.mkdir(self.tmppath('artifacts'))
        self.artifacts = LocalArtifacts('test', None, self.tmppath('state'),
                                        self.tmppath('artifacts'))

    def _create_tar(self, name, readme_contents):
        readme = self.tmppath('README')
        with open(readme, 'w') as f:
            f.write(readme_contents)
        tar = tarfile.open(self.tmppath(name), 'w:gz')
        try:
            tar.add(readme, arcname='README')
        finally:
            tar.close()
            os.unlink(readme)

    def _sample_data(self):
        self._create_tar('test.tar.gz', 'Existing data')
        os.mkdir(self.tmppath('artifacts', 'test'))
        self.test_version = '123456789000dead0000beef00001234'
        os.rename(self.tmppath('test.tar.gz'),
                  self.tmppath('artifacts', 'test',
                               'test.tar.gz.%s' % self.test_version))
        os.symlink('test.tar.gz.%s' % self.test_version,
                   self.tmppath('artifacts', 'test', 'test.tar.gz'))
        os.mkdir(self.tmppath('state', 'artifacts'))
        os.mkdir(self.tmppath('state', 'artifacts', 'test'))
        with open(self.tmppath('state', 'artifacts', 'test',
                               'test.tar.gz.versions'), 'w') as f:
            json.dump({
                'versions': [
                    {
                        'version_id': self.test_version,
                        'date_uploaded': '1970-01-01T00:00:00.000Z',
                        'metadata': {
                            'foo': 'bar',
                        },
                    },
                ],
            }, f)
        self.artifacts.versions.load()

    def test_list_empty(self):
        self.assertEqual(self.artifacts.list(), [])

    def test_upload(self):
        self._create_tar('a.tar.gz', 'Hello there')
        self.artifacts.upload(self.tmppath('a.tar.gz'))
        self.assertTMPPExists('artifacts', 'test', 'test.tar.gz')

    def test_re_upload(self):
        self._sample_data()
        symlink = self.tmppath('artifacts', 'test', 'test.tar.gz')
        old_symlink = os.readlink(symlink)

        self._create_tar('a.tar.gz', 'Hello there')
        self.artifacts.upload(self.tmppath('a.tar.gz'))
        self.assertNotEqual(os.readlink(symlink), old_symlink)

    def test_list(self):
        self._sample_data()
        self.assertEqual(self.artifacts.list(), ['test.tar.gz'])

    def test_list_subdirs(self):
        self._sample_data()
        os.mkdir(self.tmppath('artifacts', 'test', 'testing'))
        self.assertEqual(sorted(self.artifacts.list()),
                         ['test.tar.gz', 'testing/'])

    def test_download(self):
        self._sample_data()
        self.artifacts.download(dest=self.tmppath('down.tar.gz'))
        self.assertTMPPExists('down.tar.gz')

    def test_download_to_cwd(self):
        self._sample_data()
        pwd = os.getcwd()
        os.chdir(self.tmpdir)
        try:
            self.artifacts.download()
            self.assertTMPPExists('test.tar.gz')
        finally:
            os.chdir(pwd)

    def test_download_version(self):
        self._sample_data()
        dest = self.tmppath('down.tar.gz')
        self.artifacts.download(dest=dest, version=self.test_version)
        self.assertTMPPExists('down.tar.gz')

    def test_versions(self):
        self._sample_data()
        self.assertTrue(self.artifacts.versions is not None)
        self.assertTrue(self.artifacts.versions.latest is not None)

    def test_update_versions(self):
        self.artifacts.update_versions()

    def test_with_target(self):
        artifacts = LocalArtifacts('test', 'testing', self.tmppath('state'),
                                   self.tmppath('artifacts'))

        self._create_tar('a.tar.gz', 'Hello there')
        artifacts.upload(self.tmppath('a.tar.gz'))
        self.assertTMPPExists('artifacts', 'test', 'testing', 'test.tar.gz')

        self.assertEqual(artifacts.list(), ['test.tar.gz'])

        artifacts.download(self.tmppath('b.tar.gz'))
        self.assertTMPPExists('b.tar.gz')
