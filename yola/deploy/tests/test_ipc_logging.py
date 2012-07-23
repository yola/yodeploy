import StringIO
import logging
import os
import pickle
import socket
import struct
import subprocess
import sys

from . import unittest, TmpDirTestCase
from ..ipc_logging import (ExistingSocketHandler, LoggingSocketRequestHandler,
                           ThreadedLogStreamServer)


class TestExistingSocketHandler(unittest.TestCase):
    def test_handle(self):
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        sh = ExistingSocketHandler(a)
        r = logging.LogRecord('test', logging.INFO, __file__, 42,
                              'Testing 123', [], None, 'test_handle')
        # This assumes a bit of buffering...
        sh.handle(r)
        sh.close()
        size = struct.unpack('>L', b.recv(4))[0]
        received = pickle.loads(b.recv(size))
        b.close()
        self.assertIsInstance(received, dict)
        self.assertEqual(received['msg'], 'Testing 123')


class TestLoggingSocketRequestHandler(unittest.TestCase):
    def test_handle(self):
        # A dummy handler to eventually receive our message
        logger = logging.getLogger('test')
        buffer_ = StringIO.StringIO()
        handler = logging.StreamHandler(buffer_)
        logger.addHandler(handler)

        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

        # This assumes a bit of buffering...
        r = logging.LogRecord('test', logging.INFO, __file__, 42,
                              'Testing 123', [], None, 'test_handle')
        data = pickle.dumps(r.__dict__)
        a.send(struct.pack('>L', len(data)))
        a.send(data)

        # implicitly calls handle() (lovely API, eh?)
        LoggingSocketRequestHandler(b, None, None, oneshot=True)
        handler.flush()
        logger.removeHandler(handler)
        self.assertTrue(buffer_.getvalue())


class TestThreadedLogStreamServer(TmpDirTestCase):
    def test_integration(self):
        with open(self.tmppath('client.py'), 'w') as f:
            f.write("""import logging
import socket
import sys

import yola.deploy.ipc_logging

fd = int(sys.argv[1])
sock = socket.fromfd(fd, socket.AF_UNIX, socket.SOCK_STREAM)
logger = logging.getLogger('test')
handler = yola.deploy.ipc_logging.ExistingSocketHandler(sock)
logger.addHandler(handler)

logger.warn("Testing 123")
""")

        logger = logging.getLogger('test')
        logger.propegate = False
        buffer_ = StringIO.StringIO()
        handler = logging.StreamHandler(buffer_)
        logger.addHandler(handler)

        tlss = ThreadedLogStreamServer()
        p = subprocess.Popen(
            (
                'python',
                self.tmppath('client.py'),
                str(tlss.remote_socket.fileno())
            ), env={
                'PATH': os.environ['PATH'],
                'PYTHONPATH': ':'.join(sys.path),
            }, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        self.assertEqual(p.wait(), 0, 'Subprocess outputted: ' + out + err)

        handler.flush()
        logger.removeHandler(handler)
        logger.propegate = True
        self.assertTrue(buffer_.getvalue())
