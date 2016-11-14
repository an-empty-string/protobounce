from .. import util
from ..parser import parse_hostmask
from ..proto import irc_pb2, identity_pb2, cap_pb2
from concurrent import futures

import base64
import grpc
import logging
import os
import os.path
import sys
import threading

identity = identity_pb2.Identity()
nick_wait = threading.Event()
nick_set = threading.Event()
sasl_ready = threading.Event()
sasl_done = threading.Event()
sasl_success = threading.Event()

class IdentityManagerServicer(identity_pb2.IdentityManagerServicer):
    irc = None

    def GetIdentity(self, request, context):
        return identity

    def SetIdentity(self, request, context):
        return self.set_nickname(request.nickname)

    @classmethod
    def set_nickname(cls, name):
        old_nick = identity.nickname
        nick_wait.set()
        nick_set.clear()
        cls.irc.SendMessage(irc_pb2.IRCClientMessage(verb="NICK", arguments=[name]))
        nick_set.wait()

        result = identity_pb2.IdentitySet(identity=identity)
        result.success = False
        if identity.nickname != old_nick:
            result.success = True
        return result

def stop_waiting():
    if nick_wait.is_set():
        nick_wait.clear()
        nick_set.set()

def handle_messages(irc):
    messages = irc.MessageStream(irc_pb2.StreamRequest(filter=irc_pb2.MessageFilter(verbs=["NICK", "001", "433", "AUTHENTICATE", "900", "904"])))
    for message in messages:
        if message.verb == "NICK" and parse_hostmask(message.prefix)[0] == identity.nickname: # We are changing our nick
            identity.nickname = message.arguments[0]
            stop_waiting()

        elif message.verb == "001":
            identity.nickname = message.arguments[0]
            stop_waiting()

        elif message.verb == "433":
            stop_waiting()

        elif message.verb == "AUTHENTICATE":
            if message.arguments[0] == "+":
                sasl_ready.set()

        elif message.verb == "900":
            sasl_done.set()
            sasl_success.set()

        elif message.verb == "904":
            sasl_done.set()

def main(args):
    IdentityManagerServicer.irc = irc = util.get_service(args.sockets, "irc", "IRCConnection")
    server = util.get_server(args.sockets, "identity", IdentityManagerServicer)

    t = threading.Thread(target=handle_messages, args=(irc,))
    t.start()
    server.start()

    if irc.DoConnection(irc_pb2.ConnectionRequest()).result:
        if args.sasl:
            cap = util.get_service(args.sockets, "cap", "CapNegotiation")
            result = cap.RequestCap(cap_pb2.CapList(cap=["sasl"]))
            for cap in result:
                if cap.cap == "sasl":
                    irc.SendMessage(irc_pb2.IRCClientMessage(verb="AUTHENTICATE", arguments=["PLAIN"]))
                    sasl_ready.wait()

                    username, password = os.getenv("SASL_USER"), os.getenv("SASL_PASS")
                    auth_str = base64.b64encode("{0}\x00{0}\x00{1}".format(username, password).encode())
                    irc.SendMessage(irc_pb2.IRCClientMessage(verb="AUTHENTICATE", arguments=[auth_str]))
                    sasl_done.wait()

                    if sasl_success.is_set():
                        logging.info("SASL authentication complete.")
                        irc.SendMessage(irc_pb2.IRCClientMessage(verb="CAP", arguments=["END"]))
                    else:
                        logging.critical("SASL authentication failed!")
                        sys.exit(1)
                    break

            else:
                logging.critical("SASL is not available!")
                sys.exit(1)

        irc.SendMessage(irc_pb2.IRCClientMessage(verb="USER", arguments=[args.name, args.name, "+i", args.name]))
        result = IdentityManagerServicer.set_nickname(args.name)

        if not result.success:
            logging.critical("Nickname already in use!")
            sys.exit(1)

    else:
        identity.nickname = args.name

    t.join()

if __name__ == '__main__':
    import argparse
    arg_parser = argparse.ArgumentParser(description="Run the protobounce identity manager.")
    arg_parser.add_argument("--sasl", help="Use SASL authentication credentials from SASL_USER and SASL_PASS environment variables",
                            dest="sasl", action="store_true")
    arg_parser.add_argument("sockets", help="Directory of protobounce sockets")
    arg_parser.add_argument("name", help="Nickname to use")

    args = arg_parser.parse_args()
    main(args)
