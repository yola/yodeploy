import os
import sys

from yodeploy.util import extract_tar


script, extract_target, dest, stat_path = sys.argv

extract_tar(extract_target, dest)
s = os.stat(stat_path)

assert s.st_uid == 0
assert s.st_gid == 0
