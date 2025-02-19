import logging
import os
import pickle
import socket
import struct
import subprocess
import sys
from io import StringIO

from yodeploy.ipc_logging import (
    LoggingSocketRequestHandler,
    ThreadedLogStreamServer,
    ExistingSocketHandler
)
from yodeploy.tests import HelperScriptConsumer, yodeploy_location

class TestExistingSocketHandler:
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
            assert isinstance(received, dict)
            assert received['msg'] == 'Testing 123'
        finally:
            a.close()
            b.close()

class TestLoggingSocketRequestHandler:
    def setup_method(self):
        self.logger = logging.getLogger('test')
        self.buffer = StringIO()
        self.handler = logging.StreamHandler(self.buffer)
        self.logger.addHandler(self.handler)
        
        self.socket_pair = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.socket_a, self.socket_b = self.socket_pair
        self.socket_a.settimeout(2)
        self.socket_b.settimeout(2)

    def teardown_method(self):
        self.handler.flush()
        self.logger.removeHandler(self.handler)
        self.socket_a.close()
        self.socket_b.close()

    def test_handle(self):
        """Test basic message handling."""
        r = logging.LogRecord('test', logging.INFO, __file__, 42,
                            'Testing 123', [], None, 'test_handle')
        data = pickle.dumps(r.__dict__)
        self.socket_a.send(struct.pack('>L', len(data)))
        self.socket_a.send(data)

        LoggingSocketRequestHandler(self.socket_b, None, None, oneshot=True)
        size = struct.unpack('>L', self.socket_b.recv(4))[0]
        received = pickle.loads(self.socket_b.recv(size))
        assert isinstance(received, dict)
        assert received['msg'] == 'Testing 123'

    def test_filtered(self):
        """Test message filtering based on log level."""
        self.logger.setLevel(logging.WARN)
        
        r = logging.LogRecord('test', logging.INFO, __file__, 42,
                            'Testing 123', [], None, 'test_handle')
        data = pickle.dumps(r.__dict__)
        self.socket_a.send(struct.pack('>L', len(data)))
        self.socket_a.send(data)

        LoggingSocketRequestHandler(self.socket_b, None, None, oneshot=True)
        self.handler.flush()
        self.logger.removeHandler(self.handler)
        self.logger.setLevel(logging.NOTSET)
        assert not self.buffer.getvalue()

    def test_handle_multiple_records(self):
        """Test handling of multiple records."""
        messages = ["Message 1", "Message 2", "Message 3"]
        
        for msg in messages:
            r = logging.LogRecord('test', logging.INFO, __file__, 42,
                                msg, [], None, 'test_handle')
            data = pickle.dumps(r.__dict__)
            self.socket_a.send(struct.pack('>L', len(data)))
            self.socket_a.send(data)

        handler = LoggingSocketRequestHandler(
            self.socket_b, None, None, oneshot=False)
        handler_thread = threading.Thread(target=handler.handle)
        handler_thread.start()
        
        self.socket_a.close()
        handler_thread.join()
        
        output = self.buffer.getvalue().strip().split('\n')
        assert len(output) == len(messages)

class TestThreadedLogStreamServer(HelperScriptConsumer):
    def setup_method(self):
        self.server = ThreadedLogStreamServer()
        self.logger = logging.getLogger('test')
        self.logger.propagate = False
        self.buffer = StringIO()
        self.handler = logging.StreamHandler(self.buffer)
        self.logger.addHandler(self.handler)

    def teardown_method(self):
        if self.server:
            self.server.shutdown()
        self.handler.flush()
        self.logger.removeHandler(self.handler)
        self.logger.propagate = True

    def test_server_initialization(self):
        """Test server initialization and socket creation."""
        assert self.server.socket is not None
        assert self.server.remote_socket is not None
        assert self.server.remote_socket.get_inheritable()

    def test_server_shutdown(self):
        """Test server shutdown and socket cleanup."""
        socket_fd = self.server.socket.fileno()
        remote_fd = self.server.remote_socket.fileno()
        
        self.server.shutdown()
        
        try:
            os.fstat(socket_fd)
            assert False, "Socket should be closed"
        except OSError:
            pass

        try:
            os.fstat(remote_fd)
            assert False, "Remote socket should be closed"
        except OSError:
            pass

    def test_integration(self):
        """Test integration with subprocess."""
        helper_script = self.get_helper_path('tlss_user.py')
        assert os.path.exists(helper_script), f"Missing helper script: {helper_script}"

        try:
            p = subprocess.Popen(
                [sys.executable, helper_script, str(self.server.remote_socket.fileno())],
                env={
                    'PATH': os.environ['PATH'],
                    'PYTHONPATH': yodeploy_location()
                },
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            out, err = p.communicate(timeout=5)
            exit_code = p.wait()

            assert exit_code == 0, f'Subprocess outputted: {out}{err}'
            assert self.buffer.getvalue().strip()

        except subprocess.TimeoutExpired:
            p.terminate()
            raise AssertionError("Subprocess timeout expired")