"""
Provides a ThreadedLogStreamServer which receives and logs messages via socket.
Python subprocesses may make use of the provided ExistingSocketHandler loggging
handler to route log statments to a running ThreadedLogStreamServer provided
that they have a file descriptor for the socket that the TLSS instance is
listening on. Typically this is achieved by passing subprocesses an appropriate
file descriptor as an argument.
Note about Python > 3.4: File descriptors are no longer inheritable by default.
TLSS instances explicitly mark their file descriptors for the sockets they open
as inheritable so that subprocess may access them.
"""
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
    """SocketServer handler that unpickles
       log messages and forwards them to the logger."""

    def __init__(self, request, client_address, server, oneshot=False):
        self._oneshot = oneshot
        socketserver.BaseRequestHandler.__init__(self, request, client_address,
                                                 server)

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
                    return
                raise
            record = pickle.loads(buf[header_size:size])
            record = logging.makeLogRecord(record)
            logger = logging.getLogger(record.name)
            if logger.isEnabledFor(record.levelno):
                logger.handle(record)
            buf = buf[size:]

            if self._oneshot:
                break


class ThreadedLogStreamServer(socketserver.ThreadingMixIn,
                              socketserver.UnixStreamServer):
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
