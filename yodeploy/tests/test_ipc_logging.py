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
    ExistingSocketHandler, LoggingSocketRequestHandler,
    ThreadedLogStreamServer)
from yodeploy.tests import HelperScriptConsumer, yodeploy_location


class TestExistingSocketHandler(unittest.TestCase):
    def test_handle(self):
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        a.settimeout(2)
        b.settimeout(2)
        
        try:
            sh = ExistingSocketHandler(a)
            r = logging.LogRecord('test', logging.INFO, __file__, 42,
                                  'Testing 123', [], None, 'test_handle')
            sh.handle(r)
            sh.close()
            size = struct.unpack('>L', b.recv(4))[0]
            received = pickle.loads(b.recv(size))
            self.assertIsInstance(received, dict)
            self.assertEqual(received['msg'], 'Testing 123')
        finally:
            a.close()
            b.close()


class TestLoggingSocketRequestHandler(unittest.TestCase):
    def test_handle(self):
        logger = logging.getLogger('test')
        buffer_ = StringIO()
        handler = logging.StreamHandler(buffer_)
        logger.addHandler(handler)

        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        a.settimeout(2)
        b.settimeout(2)
        
        try:
            r = logging.LogRecord('test', logging.INFO, __file__, 42,
                                  'Testing 123', [], None, 'test_handle')
            data = pickle.dumps(r.__dict__)
            a.send(struct.pack('>L', len(data)))
            a.send(data)

            LoggingSocketRequestHandler(b, None, None, oneshot=True)
            size = struct.unpack('>L', b.recv(4))[0]
            received = pickle.loads(b.recv(size))
            self.assertIsInstance(received, dict)
            self.assertEqual(received['msg'], 'Testing 123')

            b.close()
        finally:
            a.close()

    def test_filtered(self):
        logger = logging.getLogger('test')
        logger.setLevel(logging.WARN)
        buffer_ = StringIO()
        handler = logging.StreamHandler(buffer_)
        logger.addHandler(handler)

        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        a.settimeout(2)
        b.settimeout(2)
        
        try:
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
            b.close()
        finally:
            a.close()


class TestThreadedLogStreamServer(unittest.TestCase, HelperScriptConsumer):
    def setUp(self):
        super().setUp()
        self.tlss = ThreadedLogStreamServer()
        self.addCleanup(self.tlss.shutdown)

    def test_integration(self):
        logger = logging.getLogger('test')
        logger.propagate = False  # Fixed typo
        buffer_ = StringIO()
        handler = logging.StreamHandler(buffer_)
        logger.addHandler(handler)

        helper_script = self.get_helper_path('tlss_user.py')
        assert os.path.exists(helper_script), f"Missing helper script: {helper_script}"

        try:
            p = subprocess.Popen(
                [sys.executable, helper_script, str(self.tlss.remote_socket.fileno())],
                env={'PATH': os.environ['PATH'], 'PYTHONPATH': yodeploy_location()},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )

            out, err = p.communicate(timeout=5)  # Prevent indefinite hanging
            exit_code = p.wait()

            self.assertEqual(exit_code, 0, f'Subprocess outputted: {out}{err}')
            self.assertTrue(buffer_.getvalue().strip())

        except subprocess.TimeoutExpired:
            p.terminate()
            self.fail("Subprocess timeout expired")
        
        finally:
            handler.flush()
            logger.removeHandler(handler)
            logger.propagate = True
