from ..parser import parse_hostmask
from ..proto import irc_pb2, identity_pb2
from concurrent import futures

import grpc
import os
import os.path
import threading

identity = identity_pb2.Identity()
nick_wait = threading.Event()
nick_set = threading.Event()


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
    messages = irc.MessageStream(irc_pb2.StreamRequest(filter=irc_pb2.MessageFilter(verbs=["NICK", "001", "433"])))
    for message in messages:
        if message.verb == "NICK" and parse_hostmask(message.prefix)[0] == identity.nickname: # We are changing our nick
            identity.nickname = message.arguments[0]
            stop_waiting()

        elif message.verb == "001":
            identity.nickname = message.arguments[0]
            stop_waiting()

        elif message.verb == "433":
            stop_waiting()

def main(args):
    channel = grpc.insecure_channel("unix:" + os.path.join(args.sockets, "irc.sock"))
    IdentityManagerServicer.irc = irc = irc_pb2.IRCConnectionStub(channel)
    t = threading.Thread(target=handle_messages, args=(irc,))
    t.start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    identity_pb2.add_IdentityManagerServicer_to_server(IdentityManagerServicer(), server)
    server.add_insecure_port("unix:" + os.path.join(args.sockets, "identity.sock"))
    server.start()

    if irc.DoConnection(irc_pb2.ConnectionRequest()).result:
        irc.SendMessage(irc_pb2.IRCClientMessage(verb="USER", arguments=[args.name, args.name, "+i", args.name]))

        result = IdentityManagerServicer.set_nickname(args.name)
        if not result.success:
            return False

    else:
        identity.nickname = args.name

    t.join()

if __name__ == '__main__':
    import argparse
    arg_parser = argparse.ArgumentParser(description="Run the protobounce identity manager.")
    arg_parser.add_argument("sockets", help="Directory of protobounce sockets")
    arg_parser.add_argument("name", help="Nickname to use")

    args = arg_parser.parse_args()
    main(args)
