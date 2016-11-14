from concurrent import futures

import grpc
import importlib
import os
import os.path

def get_service(sock_dir, service_class, service_name):
    sock_path = "unix:" + os.path.join(sock_dir, service_class + ".sock")

    service_proto = importlib.import_module("..proto." + service_class + "_pb2", __name__)
    service = getattr(service_proto, service_name + "Stub")(grpc.insecure_channel(sock_path))
    return service

def get_server(sock_dir, service_class, service_handler): # ugh sorry about the inconsistency
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    service_proto = importlib.import_module("..proto." + service_class + "_pb2", __name__)
    getattr(service_proto, "add_" + service_handler.__name__ + "_to_server")(service_handler(), server)
    server.add_insecure_port("unix:" + os.path.join(sock_dir, service_class + ".sock"))
    return server
