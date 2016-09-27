import errno
import logging
import logging.handlers
import pickle
import socket
import struct

try:
    import socketserver  # python 3
except:
    import SocketServer as socketserver  # python 2


class ExistingSocketHandler(logging.handlers.SocketHandler):
    '''A logging handler that writes to a pre-created socket'''
    def __init__(self, sock):
        logging.handlers.SocketHandler.__init__(self, None, None)
        self.sock = sock


class LoggingSocketRequestHandler(socketserver.BaseRequestHandler):
    '''A SocketServer handler that un-pickles log messages created by
    SocketHandler
    '''
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
                    break
            record = pickle.loads(buf[header_size:])
            record = logging.makeLogRecord(record)
            logger = logging.getLogger(record.name)
            if logger.isEnabledFor(record.levelno):
                logger.handle(record)
            buf = buf[size:]

            if self._oneshot:
                break


class ThreadedLogStreamServer(socketserver.ThreadingMixIn,
                              socketserver.UnixStreamServer):
    '''A Server that will receive all log messages sent over the supplied
    (already open) socket
    '''
    def __init__(self):
        self.socket, self.remote_socket = socket.socketpair(
            socket.AF_UNIX, socket.SOCK_STREAM)

        # In python >= 3.4, file descriptors are not inheritable by child
        # processes by default. We need to be able to pass the fd for
        # self.remote_socket to child processes via a command line argument
        # in various scenarios, so here we explicitly configure the fd to allow
        # for that.
        try:
            self.remote_socket.set_inheritable(True)
        except AttributeError:  # set_inheritable not available in python < 3.4
            pass

        self.RequestHandlerClass = LoggingSocketRequestHandler
        self.process_request(self.socket, None)

    def shutdown(self):
        self.socket.close()
        self.remote_socket.close()
