import socket
import struct
import pickle
import logging
import logging.handlers
import errno
import socketserver


class ExistingSocketHandler(logging.handlers.SocketHandler):
    """Logging handler that writes messages to a pre-created socket."""

    def __init__(self, sock):
        logging.handlers.SocketHandler.__init__(self, None, None)
        self.sock = sock


class LoggingSocketRequestHandler(socketserver.BaseRequestHandler):
    """SocketServer handler that unpickles log messages and forwards them to the logger."""

    _oneshot = False

    def setup(self):
        """Override setup to allow oneshot to be set dynamically."""
        if hasattr(self.server, "_oneshot"):
            self._oneshot = self.server._oneshot

    def handle(self):
        buf = b''
        header_size = struct.calcsize('>L')
        while True:
            try:
                if len(buf) < header_size:
                    buf += self.request.recv(header_size - len(buf))
                    continue

                size = struct.unpack('>L', buf[:header_size])[0] + header_size
                if len(buf) < size:
                    buf += self.request.recv(size - len(buf))
                    continue

            except IOError as e:
                if e.errno == errno.EBADF:
                    break
                raise

            record = pickle.loads(buf[header_size:size])
            record = logging.makeLogRecord(record)
            logger = logging.getLogger(record.name)
            if logger.isEnabledFor(record.levelno):
                logger.handle(record)

            buf = buf[size:]
            if self._oneshot:
                break

class ThreadedLogStreamServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    """Server that will listen for log messages sent via a socket."""
    
    def __init__(self):
        self.socket, self.remote_socket = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_STREAM)
        
        self.remote_socket.set_inheritable(True)
        self.RequestHandlerClass = LoggingSocketRequestHandler
        self.process_request(self.socket, None)

    def shutdown(self):
        """Close open sockets."""
        self.socket.close()
        self.remote_socket.close()