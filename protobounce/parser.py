from .proto import irc_pb2

def parse_hostmask(hostmask: str) -> list:
    ret = []
    if "!" in hostmask:
        first, hostmask = hostmask.split("!", maxsplit=1)
        ret.append(first)

    if "@" in hostmask:
        first, hostmask = hostmask.split("@", maxsplit=1)
        ret.append(first)

    ret.append(hostmask)
    return ret


def message_from_str(message: str) -> irc_pb2.IRCServerMessage:
    obj = irc_pb2.IRCServerMessage()

    if isinstance(message, bytes):
        message = message.decode("UTF-8", "replace")

    s = message.split(" ")
    if s[0].startswith("@"):
        tag_str = s[0][1:].split(";")
        s = s[1:]

        for tag in tag_str:
            tag_info = tag.split('=', 1)

            this_tag = obj.tags.add()
            this_tag.key = tag_info[0]
            if len(tag_info) > 1:
                this_tag.value = tag_info[1]

    if s[0].startswith(":"):
        obj.prefix = s[0][1:]
        s = s[1:]

    obj.verb = s[0].upper()
    s = s[1:]

    for idx, param in enumerate(s):
        if param.startswith(":"):
            obj.arguments.append(' '.join(s[idx:])[1:])
            break
        obj.arguments.append(param)

    return obj

def str_from_message(message: irc_pb2.IRCClientMessage) -> str:
    ret = ""
    if len(message.tags):
        tags = []
        for tag in message.tags:
            this_tag = tag.key
            if tag.value:
                this_tag += "={}".format(tag.value)
            tags.append(this_tag)
        ret += "@" + ";".join(tags) + " "

    ret += message.verb.upper() + " "
    ret += " ".join(message.arguments[:-1])

    if message.arguments:
        ret += " :" + message.arguments[-1]

    return ret
