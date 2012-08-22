import os
import shutil
import sys
import tarfile
import tempfile

unittest = None
if sys.version_info >= (2, 7):
    import unittest
    hush_pyflakes = unittest
else:
    import unittest2 as unittest


class TmpDirTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='yola.deploy-test')

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def tmppath(self, *fragments):
        return os.path.join(self.tmpdir, *fragments)

    def mkdir(self, *fragments):
        os.makedirs(self.tmppath(*fragments))

    def create_tar(self, name, *paths, **kwargs):
        contents = kwargs.get('contents', {})
        for path in paths:
            contents.setdefault(path, 'foo bar baz\n')
        pwd = os.getcwd()
        os.mkdir(self.tmppath('create_tar_workdir'))
        os.chdir(self.tmppath('create_tar_workdir'))
        roots = set()
        try:
            for pathname, data in contents.iteritems():
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
