from tempfile import mkdtemp
import json
import os
import shutil
import unittest

# TODO: This must go
class AttrDict(dict):
    __getattr__ = dict.__getitem__
import imp
import sys
sys.modules['config'] = imp.new_module('config')
deploy = imp.new_module('config.deploy')
deploy.deploy_settings = AttrDict({
    'artifacts': AttrDict({
        'provider': 'local',
    })
})
sys.modules['config.deploy'] = deploy

from yola.deploy.artifacts import ArtifactVersions

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


class TestArtifactiVersions(unittest.TestCase):
    def setUp(self):
        self.tmpdir = mkdtemp(prefix='yola.deploy-test')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    @property
    def _test_fn(self):
        return os.path.join(self.tmpdir, 'test.json')

    def _write_test_json(self):
        with open(self._test_fn, 'w') as f:
            f.write(TEST_JSON)

    def testLoad(self):
        self._write_test_json()
        av = ArtifactVersions(self._test_fn)
        self.assertEqual(len(av.versions), 2)

    def testSave(self):
        av = ArtifactVersions(self._test_fn)
        for version in TEST_VERSIONS['versions']:
            av.add_version(version['version_id'], version['date_uploaded'],
                           version['metadata'])
        av.save()
        with open(self._test_fn, 'r') as f:
            self.assertEqual(json.load(f), TEST_VERSIONS)
