from ..proto import cap_pb2, irc_pb2
from collections import defaultdict
from concurrent import futures
from threading import Event, Semaphore

import grpc

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
    def RequestCap(self, request, context):
        waiting_on = []
        for cap in request.cap:
            cap = cap.upper()

            if cap in have_caps:
                yield cap_pb2.SingleCap(cap)
            else:
                irc.SendMessage(irc_pb2.IRCClientMessage(verb="CAP", arguments=["REQ", cap]))
                waiting_on.append(cap)

        while waiting_on:
            e = wait_on(*[waiting_caps[i] for i in waiting_on])
            e.wait()
            e.clear()

            done = [j[0] for j in [(i, waiting_caps[i].is_set()) for i in waiting_on] if not j[1]]
            waiting_on.remove(done)
            if done in have_caps:
                yield cap_pb2.SingleCap(cap_pb2)

    def GetCaps(self, request, context):
        return cab_pb2.CapList(cap=have_caps)
