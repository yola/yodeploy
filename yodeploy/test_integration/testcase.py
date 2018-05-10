import os
from unittest import TestCase


class DeployTestCase(TestCase):
    def assertDeployed(self, fn):
        deployed_file = os.path.join(os.path.dirname(__file__), 'filesys', fn)
        self.assertTrue(
            os.path.exists(deployed_file),
            msg='%s does not exist' % deployed_file
        )
