
from ..repository import version_sort_key
from . import unittest, TmpDirTestCase


class TestVersionSortKey(unittest.TestCase):
    def test_digits(self):
        unsorted = ['1', '10', '2']
        expected = ['1', '2', '10']
        unsorted.sort(key=version_sort_key)
        self.assertEqual(unsorted, expected)

    def test_alpha(self):
        unsorted = ['c', 'ba', 'b']
        expected = ['b', 'ba', 'c']
        unsorted.sort(key=version_sort_key)
        self.assertEqual(unsorted, expected)

    def test_mixed(self):
        unsorted = ['abc', 'a1b', 'a10b', 'a2b', 'a1', 'abc1']
        expected = ['a1', 'a1b', 'a2b', 'a10b', 'abc', 'abc1']
        unsorted.sort(key=version_sort_key)
        self.assertEqual(unsorted, expected)


class TestLocalRepository(TmpDirTestCase):
    pass
