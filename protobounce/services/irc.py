from collections import defaultdict
from concurrent import futures
from ..proto import irc_pb2
from queue import Queue

import argparse
import grpc
import logging
import parser
import socket
import ssl
import threading
import time

pending = defaultdict(Queue)
send_pending = Queue()

logging.basicConfig(level=logging.DEBUG)

class IRCConnectionServicer(irc_pb2.IRCConnectionServicer):
    def MessageStream(self, request, context):
        queue = pending[request.connection_id]
        while True:
            yield queue.get()
            queue.task_done()

    def SendMessage(self, request, context):
        send_pending.put(request)
        return irc_pb2.SentResponse()

class IRCConnection(object):
    def __init__(self, host, port, ssl):
        self.handlers = {"PING": self.handle_ping}
        self.host = host
        self.port = port

        self.s = ssl.SSLSocket() if ssl else socket.socket()

        self.read_thread = threading.Thread(target=self.handle_socket_read)
        self.write_thread = threading.Thread(target=self.handle_socket_write)

    def connect(self):
        self.s.connect((self.host, self.port))

    def handle_ping(self, writeln, msg):
        writeln("PONG {}".format(msg.arguments[0] if msg.arguments else ""))

    def listen(self):
        self.read_thread.start()
        self.write_thread.start()

    def handle(self, msg):
        if msg.verb in self.handlers:
            self.handlers[msg.verb](self.writeln, msg)

        else:
            for _, q in pending.items():
                q.put(msg)

    def writeln(self, x):
        logging.debug("Send: {}".format(x))

        if not isinstance(x, bytes):
            x = x.encode()
        self.s.send(x + b"\r\n")

    def handle_socket_read(self):
        endl = b"\n"
        buf = b""
        while True:
            while endl in buf:
                msg, buf = buf.split(endl, maxsplit=1)
                msg = msg.strip().decode()
                logging.debug("Recv: {}".format(msg))
                parsed = parser.message_from_str(msg)
                self.handle(parsed)

            buf += self.s.recv(256)

    def handle_socket_write(self):
        while True:
            msg = send_pending.get()
            unparsed = parser.str_from_message(msg)
            self.writeln(unparsed)

def irc_connect(host, port, ssl):
    c = IRCConnection(host, port, ssl)
    c.listen()
    return c

def create_server(port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    irc_pb2.add_IRCConnectionServicer_to_server(IRCConnectionServicer(), server)
    server.add_insecure_port(port)
    return server

def serve_forever(server):
    server.start()
    while True:
        time.sleep(86400)

if __name__ == '__main__':
    import argparse
    arg_parser = argparse.ArgumentParser(description="Run the protobounce IRC server.")
    arg_parser.add_argument("listen", help="Address to listen on")
    arg_parser.add_argument("host", help="IRC server to connect to")
    arg_parser.add_argument("port", type=int, help="IRC port to use")
    arg_parser.add_argument("--secure", dest="ssl", action="store_true", help="Use SSL/TLS to connect")
    args = arg_parser.parse_args()

    server = create_server(args.listen)
    conn = irc_connect(args.host, args.port, args.ssl)
    serve_forever(server)
