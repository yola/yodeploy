import logging
import socket
import sys

from yodeploy import ipc_logging

fd = int(sys.argv[1])
sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
logger = logging.getLogger('test')
handler = ipc_logging.ExistingSocketHandler(sock)
logger.addHandler(handler)

logger.warn("Testing 123")
