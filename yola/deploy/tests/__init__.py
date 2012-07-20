import os
import shutil
import sys
import tempfile

if sys.version_info >= (2, 7):
    import unittest
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
