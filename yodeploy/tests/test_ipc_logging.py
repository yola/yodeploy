import logging
import os
import pickle
import socket
import struct
import subprocess
import sys
import unittest
from io import StringIO

from yodeploy.ipc_logging import (
    LoggingSocketRequestHandler,
    ThreadedLogStreamServer,
    ExistingSocketHandler
)
from yodeploy.tests import HelperScriptConsumer, yodeploy_location


class TestExistingSocketHandler(unittest.TestCase):
    def test_handle(self):
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        sh = ExistingSocketHandler(a)
        r = logging.LogRecord('test', logging.INFO, __file__, 42,
                              'Testing 123', [], None, 'test_handle')
        sh.handle(r)
        sh.close()
        size = struct.unpack('>L', b.recv(4))[0]
        received = pickle.loads(b.recv(size))
        b.close()
        self.assertIsInstance(received, dict)
        self.assertEqual(received['msg'], 'Testing 123')

class TestLoggingSocketRequestHandler(unittest.TestCase):
    def test_handle(self):
        logger = logging.getLogger('test')
        buffer_ = StringIO()
        handler = logging.StreamHandler(buffer_)
        logger.addHandler(handler)
        
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        r = logging.LogRecord('test', logging.INFO, __file__, 42,
                              'Testing 123', [], None, 'test_handle')
        data = pickle.dumps(r.__dict__)
        a.send(struct.pack('>L', len(data)))
        a.send(data)
        
        LoggingSocketRequestHandler(b, None, None, oneshot=True)
        handler.flush()
        logger.removeHandler(handler)
        self.assertTrue(buffer_.getvalue())
    
    def test_filtered(self):
        logger = logging.getLogger('test')
        logger.setLevel(logging.WARN)
        buffer_ = StringIO()
        handler = logging.StreamHandler(buffer_)
        logger.addHandler(handler)

        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        r = logging.LogRecord('test', logging.INFO, __file__, 42,
                              'Testing 123', [], None, 'test_handle')
        data = pickle.dumps(r.__dict__)
        a.send(struct.pack('>L', len(data)))
        a.send(data)
        
        LoggingSocketRequestHandler(b, None, None, oneshot=True)
        handler.flush()
        logger.removeHandler(handler)
        logger.setLevel(logging.NOTSET)
        self.assertFalse(buffer_.getvalue())

class TestThreadedLogStreamServer(unittest.TestCase, HelperScriptConsumer):
    def setUp(self):
        super().setUp()
        self.tlss = ThreadedLogStreamServer()
        self.addCleanup(self.tlss.shutdown)
    
    def test_integration(self):
        logger = logging.getLogger('test')
        logger.propagate = False
        buffer_ = StringIO()
        handler = logging.StreamHandler(buffer_)
        logger.addHandler(handler)
        
        p = subprocess.Popen([
                sys.executable,
                self.get_helper_path('tlss_user.py'),
                str(self.tlss.remote_socket.fileno())
            ], env={
                'PATH': os.environ['PATH'],
                'PYTHONPATH': yodeploy_location(),
            }, stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=False,
            universal_newlines=True)
        out, err = p.communicate()

        self.assertEqual(p.wait(), 0, f'Subprocess outputted: {out}{err}')
        handler.flush()
        logger.removeHandler(handler)
        logger.propagate = True
        self.assertTrue(buffer_.getvalue())
