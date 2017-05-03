import os
import shutil
import tarfile
import tempfile
import unittest


class TmpDirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='yodeploy-test')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def tmppath(self, *fragments):
        return os.path.join(self.tmpdir, *fragments)

    def mkdir(self, *fragments):
        path = self.tmppath(*fragments)
        os.makedirs(path)
        return path

    def create_tar(self, name, *paths, **kwargs):
        contents = kwargs.get('contents', {})
        for path in paths:
            contents.setdefault(path, 'foo bar baz\n')
        pwd = os.getcwd()
        os.mkdir(self.tmppath('create_tar_workdir'))
        os.chdir(self.tmppath('create_tar_workdir'))
        roots = set()
        try:
            for pathname, data in contents.items():
                if '/' in pathname:
                    if not os.path.exists(os.path.dirname(pathname)):
                        os.makedirs(os.path.dirname(pathname))
                roots.add(pathname.split('/', 1)[0])
                with open(pathname, 'w') as f:
                    f.write(data)

            tar = tarfile.open(self.tmppath(name), 'w:gz')
            try:
                for pathname in list(roots):
                    tar.add(pathname)
            finally:
                tar.close()
        finally:
            os.chdir(pwd)
        shutil.rmtree(self.tmppath('create_tar_workdir'))

    def assertTMPPExists(self, *fragments, **kwargs):
        msg = kwargs.get('msg', None)
        if not os.path.exists(self.tmppath(*fragments)):
            self.fail(self._formatMessage(msg,
                "does not exist: %s" % (os.path.join(*fragments))))

    def assertNotTMPPExists(self, *fragments, **kwargs):
        msg = kwargs.get('msg', None)
        if os.path.exists(self.tmppath(*fragments)):
            self.fail(self._formatMessage(msg,
                "does not exist: %s" % (os.path.join(*fragments))))

    def assertTMPPContents(self, contents, *fragments):
        with open(self.tmppath(*fragments)) as f:
            self.assertEqual(f.read(), contents)


class HelperScriptConsumer(object):
    """Mixin thats adds helpers for calling test script subprocesses."""

    def get_helper_path(self, name):
        helpers = os.path.join(os.path.dirname(__file__), 'helper_scripts')
        return os.path.join(helpers, name)


def yodeploy_location():
    import yodeploy
    return os.path.dirname(os.path.abspath(yodeploy.__path__[0]))
