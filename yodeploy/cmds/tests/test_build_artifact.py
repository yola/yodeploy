# -*- coding: utf-8 -*-
from yodeploy.cmds.build_artifact import GitHelper
from unittest import TestCase
from mock import patch


class TestGitHelper(TestCase):

    def setUp(self):
        self.patcher = patch('yodeploy.cmds.build_artifact.check_output')
        self.check_output = self.patcher.start()
        self.git = GitHelper()

    def cleanUp(self):
        self.patcher.stop()

    def test_uses_get_show_for_the_commit_message(self):
        self.check_output.return_value = 'my commit message'
        self.assertEqual(self.git.commit_msg, 'my commit message')
        git_call = self.check_output.call_args[0][0][0:2]
        self.assertEqual(git_call, ('git', 'show'))

    def test_removes_special_chars_from_the_commit_message(self):
        self.check_output.return_value = 'frosty the ☃'
        self.assertEqual(self.git.commit_msg, 'frosty the ?')
