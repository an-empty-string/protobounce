from ..proto import irc_pb2

import grpc

def main(args):
    channel = grpc.insecure_channel(args.connect)
    irc = irc_pb2.IRCConnectionStub(channel)
    irc.SendMessage(irc_pb2.IRCClientMessage(verb="USER", arguments=[args.name, args.name, "+i", args.name]))
    irc.SendMessage(irc_pb2.IRCClientMessage(verb="NICK", arguments=[args.name]))
    irc.DoConnection(irc_pb2.ConnectionRequest())

if __name__ == '__main__':
    import argparse
    arg_parser = argparse.ArgumentParser(description="Run the protobounce identity manager.")
    arg_parser.add_argument("connect", help="Address of protobounce IRC service")
    arg_parser.add_argument("name", help="Nickname to use")

    args = arg_parser.parse_args()
    main(args)
