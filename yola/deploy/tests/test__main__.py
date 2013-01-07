import os
import subprocess
import sys

from . import TmpDirTestCase


class TestHookery(TmpDirTestCase):
    def test_hook(self):
        self.mkdir('artifacts')
        self.mkdir('test', 'versions', 'foo', 'deploy')
        with open(self.tmppath('test', 'versions', 'foo', 'deploy',
                               'hooks.py'), 'w') as f:
            f.write("""import os

from yola.deploy.hooks.base import DeployHook


class Hooks(DeployHook):
    def prepare(self):
        open(os.path.join(self.root, 'hello'), 'w').close()


hooks = Hooks
""")
        with open(self.tmppath('config.py'), 'w') as f:
            f.write("""import os

from yola.deploy.artifacts import AttrDict


prefix='%s'
deploy_settings = AttrDict(
    paths=AttrDict(
        artifacts=os.path.join(prefix, 'artifacts'),
    ),
    artifacts=AttrDict(
        provider='local',
    ),
)
""" % self.tmpdir)
        # .__main__ is needed for silly Python 2.6
        # See http://bugs.python.org/issue2751
        p = subprocess.Popen((
                'python', '-m', 'yola.deploy.__main__',
                '--config', self.tmppath('config.py'),
                '--app', 'test',
                '--hook', 'prepare',
                self.tmppath('test'),
                'foo',
            ), env={
                'PATH': os.environ['PATH'],
                'PYTHONPATH': ':'.join(sys.path),
            }, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        self.assertEqual(p.wait(), 0, 'Subprocess outputted: ' + out + err)
        self.assertTMPPExists('test', 'hello')
