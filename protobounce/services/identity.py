from ..parser import parse_hostmask
from ..proto import irc_pb2, identity_pb2
from concurrent import futures

import grpc
import threading

identity = identity_pb2.Identity()
nick_wait = threading.Event()
nick_set = threading.Event()

global irc
irc = None

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

def set_nickname(name):
    old_nick = identity.nickname
    nick_wait.set()
    nick_set.clear()
    irc.SendMessage(irc_pb2.IRCClientMessage(verb="NICK", arguments=[name]))
    nick_set.wait()

    result = identity_pb2.IdentitySet(identity=identity)
    result.success = False
    if identity.nickname != old_nick:
        result.success = True
    return result

class IdentityManagerServicer(identity_pb2.IdentityManagerServicer):
    def GetIdentity(self, request, context):
        return identity

    def SetIdentity(self, request, context):
        return set_nickname(request.nickname)

def main(args):
    global irc

    channel = grpc.insecure_channel(args.connect)
    irc = irc_pb2.IRCConnectionStub(channel)
    t = threading.Thread(target=handle_messages, args=(irc,))
    t.start()

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    identity_pb2.add_IdentityManagerServicer_to_server(IdentityManagerServicer(), server)
    server.add_insecure_port(args.listen)
    server.start()

    if irc.DoConnection(irc_pb2.ConnectionRequest()).result:
        irc.SendMessage(irc_pb2.IRCClientMessage(verb="USER", arguments=[args.name, args.name, "+i", args.name]))

        result = set_nickname(args.name)
        if not result.success:
            return False

    else:
        identity.nickname = args.name

    t.join()

if __name__ == '__main__':
    import argparse
    arg_parser = argparse.ArgumentParser(description="Run the protobounce identity manager.")
    arg_parser.add_argument("listen", help="Address to listen on")
    arg_parser.add_argument("connect", help="Address of protobounce IRC service")
    arg_parser.add_argument("name", help="Nickname to use")

    args = arg_parser.parse_args()
    main(args)
