import os
import subprocess
import sys

from yodeploy.tests import TmpDirTestCase, yodeploy_location


class TestHookery(TmpDirTestCase):
    def test_hook(self):
        self.mkdir('artifacts')
        self.mkdir('test', 'versions', 'foo', 'deploy')
        with open(self.tmppath('test', 'versions', 'foo', 'deploy',
                               'hooks.py'), 'w') as f:
            f.write("""import os

from yodeploy.hooks.base import DeployHook


class Hooks(DeployHook):
    def prepare(self):
        open(os.path.join(self.root, 'hello'), 'w').close()


hooks = Hooks
""")
        with open(self.tmppath('config.py'), 'w') as f:
            f.write("""import os

class AttrDict(dict):
    __getattr__ = dict.__getitem__

deploy_settings = AttrDict(
    artifacts=AttrDict(
        store='local',
        store_settings=AttrDict(
            local=AttrDict(
                directory=os.path.join('%s', 'artifacts'),
            ),
        ),
    ),
)
""" % self.tmpdir)
        p = subprocess.Popen((
                sys.executable, '-m', 'yodeploy',
                '--config', self.tmppath('config.py'),
                '--app', 'test',
                '--hook', 'prepare',
                self.tmppath('test'),
                'foo',
            ), env={
                'PATH': os.environ['PATH'],
                'PYTHONPATH': yodeploy_location(),
            }, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True)
        out, err = p.communicate()

        self.assertEqual(
            p.wait(), 0, 'Subprocess outputted: %s%s' % (out, err))
        self.assertTMPPExists('test', 'hello')
