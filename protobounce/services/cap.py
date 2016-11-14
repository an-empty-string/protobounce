from .. import util
from ..proto import cap_pb2, irc_pb2
from collections import defaultdict
from concurrent import futures
from threading import Event, Semaphore, Thread

import grpc
import logging
import os
import os.path

logging.basicConfig(level=logging.DEBUG)

waiting_caps = defaultdict(Event)
have_caps = set()

def wait_on(*e):
    any_event = Event()
    stop = Event()

    def wait_specifically_on(e):
        e.wait()
        if not stop.is_set():
            any_event.set()
            stop.set()

    for event in e:
        Thread(target=wait_specifically_on, args=(event,)).start()

    return any_event

class CapNegotiationServicer(cap_pb2.CapNegotiationServicer):
    irc = None

    def RequestCap(self, request, context):
        waiting_on = []
        for cap in request.cap:
            cap = cap.lower()

            if cap in have_caps:
                yield cap_pb2.SingleCap(cap=cap)
            elif waiting_caps[cap].is_set():
                continue
            else:
                self.irc.SendMessage(irc_pb2.IRCClientMessage(verb="CAP", arguments=["REQ", cap]))
                waiting_on.append(cap)

        while waiting_on:
            e = wait_on(*[waiting_caps[i] for i in waiting_on])
            e.wait()
            e.clear()

            done = [j[0] for j in [(i, waiting_caps[i].is_set()) for i in waiting_on] if j[1]]
            for thing in done:
                waiting_on.remove(thing)

                if thing in have_caps:
                    yield cap_pb2.SingleCap(cap=thing)

    def GetCaps(self, request, context):
        return cap_pb2.CapList(cap=have_caps)

def handle_messages(irc):
    messages = irc.MessageStream(irc_pb2.StreamRequest(filter=irc_pb2.MessageFilter(verbs=["CAP"])))
    for message in messages:
        if message.verb != "CAP":
            continue

        action = message.arguments[1].upper()

        if action == "ACK" or action == "NAK":
            caps = message.arguments[2].lower().split()
            for cap in caps:
                if action == "ACK":
                    logging.info("Got ACK for {}".format(cap))
                    have_caps.add(cap)
                else:
                    logging.info("Got NAK for {}".format(cap))
                waiting_caps[cap].set()

def main(args):
    CapNegotiationServicer.irc = irc = util.get_service(args.sockets, "irc", "IRCConnection")
    server = util.get_server(args.sockets, "cap", CapNegotiationServicer)

    server.start()
    handle_messages(irc)

if __name__ == '__main__':
    import argparse
    arg_parser = argparse.ArgumentParser(description="Run the protobounce capability manager.")
    arg_parser.add_argument("sockets", help="Directory of protobounce sockets")

    args = arg_parser.parse_args()
    main(args)
