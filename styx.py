# styx.py - Classes to decode and encode Styx (9P2000) messages.
#
# Copyright (C) 2018 David Boddie <david@boddie.org.uk>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Using the information from the Inferno man 5 pages.

import struct

class StringReceiver:

    def __init__(self, string):
        self.string = string
        self.ptr = 0
    
    def recv(self, n):
        end = self.ptr + n
        data = self.string[self.ptr:end]
        self.ptr = end
        return data


class SocketReceiver:

    def __init__(self, sock):
        self.sock = sock
    
    def recv(self, n):
        data = ""
        while len(data) < n:
            data += self.sock.recv(n - len(data))
        
        return data


def decode_string(stream):

    length = struct.unpack("<H", stream.recv(2))[0]
    if length > 0:
        return stream.recv(length).decode("utf8")
    else:
        return u""
    
def encode_string(string):

    utf8 = string.encode("utf8")
    return struct.pack("<H", len(utf8)) + utf8

def decode_data(stream):

    n = struct.unpack("<H", stream.recv(2))[0]
    return stream.recv(n)

def encode_data(data):

    return struct.pack("<H", len(data)) + data

def decode_qid(stream):

    # Store a tuple of values: file/dir, qid version, qid path.
    return struct.unpack("<BIQ", stream.recv(13))

def encode_qid(qid):

    return struct.pack("<BIQ", *qid)

def decode_format(stream, obj):

    for name, length in obj.format:
    
        if length == "s":
            # UTF-8 string
            value = decode_string(stream)
        elif length == "n":
            # n bytes of raw data
            value = decode_data(stream)
        elif length == 1:
            value = struct.unpack("<B", stream.recv(1))[0]
        elif length == 2:
            value = struct.unpack("<H", stream.recv(2))[0]
        elif length == 4:
            value = struct.unpack("<I", stream.recv(4))[0]
        elif length == 8:
            value = struct.unpack("<Q", stream.recv(8))[0]
        elif name == "qid":
            value = decode_qid(stream)
        elif name == "stat":
            value = Stat()
            value.decode(stream)
        elif length in obj.__dict__:
            value = stream.recv(obj.__dict__[length])
        else:
            raise StyxError("decode_format: Unknown field length specifier: %s" % length)
        
        obj.__dict__[name] = value

def encode_format(stream, obj):

    data = ""
    
    for name, length in obj.format:
    
        value = obj.__dict__[name]
        
        if length == "s":
            # UTF-8 string
            data += encode_string(value)
        elif length == "n":
            # n bytes of raw data
            data += encode_data(value)
        elif length == 1:
            data += struct.pack("<B", value)
        elif length == 2:
            data += struct.pack("<H", value)
        elif length == 4:
            data += struct.pack("<I", value)
        elif length == 8:
            data += struct.pack("<Q", value)
        elif name == "qid":
            data += encode_qid(value)
        elif name == "stat":
            data += value.encode()
        else:
            data += value
    
    return data


class StyxError(Exception):
    pass


class StyxMessage:

    def init(self, size, tag):
    
        self.size = size
        self.tag = tag
    
    def __repr__(self):
    
        s = self.msg_name + "(tag=" + repr(self.tag)
        
        for name, length in self.format:
            s += ", " + "%s=%s" % (name, repr(self.__dict__[name]))
        
        return s + ")"
    
    def decode(self, size, tag, stream):
    
        self.init(size, tag)
        decode_format(stream, self)
        return self
    
    def encode(self, stream):
    
        # Start with the message type and tag before adding all the other pieces.
        data = struct.pack("<BH", self.code, self.tag)
        data += encode_format(stream, self)
        
        # Finally, prepend the length to the byte string and send it.
        data = struct.pack("<I", len(data) + 4) + data
        stream.sendall(data)


class Tversion(StyxMessage):

    msg_name = "Tversion"
    code = 100
    format = [("msize", 4), ("version", "s")]
    
    def __init__(self, tag = None, msize = 0, version = ""):
    
        self.tag = tag
        self.msize = msize
        self.version = version

class Rversion(StyxMessage):

    msg_name = "Rversion"
    code = 101
    format = [("msize", 4), ("version", "s")]
    
    def __init__(self, tag = None, msize = 0, version = ""):
    
        self.tag = tag
        self.msize = msize
        self.version = version


class Tattach(StyxMessage):

    msg_name = "Tattach"
    code = 104
    format = [("fid", 4), ("afid", 4), ("uname", "s"), ("aname", "s")]
    
    NOFID = 0xffffffff
    
    def __init__(self, tag = None, fid = None, afid = None, uname = None, aname = None):
    
        self.tag = tag
        self.fid = fid
        self.afid = afid
        self.uname = uname
        self.aname = aname

class Rattach(StyxMessage):

    msg_name = "Rattach"
    code = 105
    format = [("qid", 13)]
    
    def __init__(self, tag = None, qid = None):
    
        self.tag = tag
        self.qid = qid


class Rerror(StyxMessage):

    msg_name = "Rerror"
    code = 107
    format = [("ename", "s")]
    
    def __init__(self, tag = None, ename = None):
    
        self.tag = tag
        self.ename = ename


class Twalk(StyxMessage):

    msg_name = "Twalk"
    code = 110
    format = [("fid", 4), ("newfid", 4), ("nwname", 2)] # nwname of wname[s]
    
    def __init__(self, tag = None, fid = None, newfid = None, wname = []):
    
        self.tag = tag
        self.fid = fid
        self.newfid = newfid
        self.wname = wname
        self.nwname = len(wname)
    
    def decode(self, size, tag, stream):
    
        StyxMessage.decode(self, size, tag, stream)
        
        # Decode the names.
        self.wname = []
        i = 0
        while i < self.nwname:
            self.wname.append(decode_string(stream))
            i += 1
        
        return self
    
    def encode(self, stream):
    
        data = struct.pack("<BH", self.code, self.tag)
        
        self.nwname = len(self.wname)
        data += encode_format(stream, self)
        
        # Encode the names separately.
        for name in self.wname:
            data += encode_string(name)
        
        data = struct.pack("<I", len(data) + 4) + data
        stream.sendall(data)

class Rwalk(StyxMessage):

    msg_name = "Rwalk"
    code = 111
    format = [("nwqid", 2)] # nwqid of wqid[13]
    
    def __init__(self, tag = None, wqid = []):
    
        self.tag = tag
        self.wqid = wqid
        self.nwqid = len(wqid)
    
    def decode(self, size, tag, stream):
    
        StyxMessage.decode(self, size, tag, stream)
        
        # Decode the qids.
        self.wqid = []
        i = 0
        while i < self.nwqid:
            self.wqid.append(decode_qid(stream))
            i += 1
        
        return self
    
    def encode(self, stream):
    
        data = struct.pack("<BH", self.code, self.tag)
        
        self.nwqid = len(self.wqid)
        data += encode_format(stream, self)
        
        # Encode the qids separately.
        for qid in self.wqid:
            data += encode_qid(qid)
        
        data = struct.pack("<I", len(data) + 4) + data
        stream.sendall(data)


class Topen(StyxMessage):

    msg_name = "Topen"
    code = 112
    format = [("fid", 4), ("mode", 1)]
    
    def __init__(self, tag = None, fid = None, mode = None):
    
        self.tag = tag
        self.fid = fid
        self.mode = mode

class Ropen(StyxMessage):

    msg_name = "Ropen"
    code = 113
    format = [("qid", 13), ("iounit", 4)]
    
    def __init__(self, tag = None, qid = None, iounit = None):
    
        self.tag = tag
        self.qid = qid
        self.iounit = iounit


class Tcreate(StyxMessage):

    msg_name = "Tcreate"
    code = 114
    format = [("fid", 4), ("name", "s"), ("perm", 4), ("mode", 1)]
    
    def __init__(self, tag = None, fid = None, name = "", perm = 0, mode = None):
    
        self.tag = tag
        self.fid = fid
        self.name = name
        self.perm = perm
        self.mode = mode

class Rcreate(StyxMessage):

    msg_name = "Rcreate"
    code = 115
    format = [("qid", 13), ("iounit", 4)]
    
    def __init__(self, tag = None, qid = None, iounit = None):
    
        self.tag = tag
        self.qid = qid
        self.iounit = iounit


class Tread(StyxMessage):

    msg_name = "Tread"
    code = 116
    format = [("fid", 4), ("offset", 8), ("count", 4)]
    
    def __init__(self, tag = None, fid = None, offset = 0, count = 0):
    
        self.tag = tag
        self.fid = fid
        self.offset = offset
        self.count = count

class Rread(StyxMessage):

    msg_name = "Rread"
    code = 117
    format = [("count", 4), ("data", "count")]
    
    def __init__(self, tag = None, data = ""):
    
        self.tag = tag
        self.data = data
        self.count = len(data)


class Twrite(StyxMessage):

    msg_name = "Twrite"
    code = 118
    format = [("fid", 4), ("offset", 8), ("count", 4), ("data", "count")]
    
    def __init__(self, tag = None, fid = None, offset = 0, data = ""):
    
        self.tag = tag
        self.fid = fid
        self.offset = offset
        self.count = len(data)
        self.data = data

class Rwrite(StyxMessage):

    msg_name = "Rwrite"
    code = 119
    format = [("count", 4)]
    
    def __init__(self, tag = None, count = 0):
    
        self.tag = tag
        self.count = count


class Tclunk(StyxMessage):

    msg_name = "Tclunk"
    code = 120
    format = [("fid", 4)]
    
    def __init__(self, tag = None, fid = None):
    
        self.tag = tag
        self.fid = fid

class Rclunk(StyxMessage):

    msg_name = "Rclunk"
    code = 121
    format = []
    
    def __init__(self, tag = None):
    
        self.tag = tag


class Tremove(StyxMessage):

    msg_name = "Tremove"
    code = 122
    format = [("fid", 4)]
    
    def __init__(self, tag = None, fid = None):
    
        self.tag = tag
        self.fid = fid

class Rremove(StyxMessage):

    msg_name = "Rremove"
    code = 123
    format = []
    
    def __init__(self, tag = None):
    
        self.tag = tag


class Tstat(StyxMessage):

    msg_name = "Tstat"
    code = 124
    format = [("fid", 4)]
    
    def __init__(self, tag = None, fid = None):
    
        self.tag = tag
        self.fid = fid

class Rstat(StyxMessage):

    msg_name = "Rstat"
    code = 125
    # Because the format of this message describes the stat information as
    # stat[n] it includes a 16-bit length, but the stat object itself
    # includes its own length field.
    format = [("stat_size", 2), ("stat", "stat")]
    
    def __init__(self, tag = None, stat = None):
    
        self.tag = tag
        self.stat = stat
    
    def __repr__(self):
    
        return self.msg_name + "(tag=%s, stat=%s)" % (repr(self.tag), repr(self.stat))
    
    def encode(self, stream):
    
        # Encode the stat structure.
        stat_data = self.stat.encode()
        
        # Prepend the size of the stat structure itself.
        stat_data = encode_data(stat_data)
        
        data = struct.pack("<BH", self.code, self.tag) + stat_data
        
        data = struct.pack("<I", len(data) + 4) + data
        stream.sendall(data)


class Stat:

    DMDIR    = 0x80000000
    DMAPPEND = 0x40000000
    DMEXCL   = 0x20000000
    DMTMP    = 0x04000000
    
    format = [
        ("size", 2), ("type", 2), ("dev", 4), ("qid", 13), ("mode", 4),
        ("atime", 4), ("mtime", 4), ("length", 8), ("name", "s"), ("uid", "s"),
        ("gid", "s"), ("muid", "s")
        ]
    
    def __init__(self, type = 0, dev = 0, qid = (0, 0, 0), mode = 0,
                       atime = 0, mtime = 0, length = 0, name = u"", uid = u"",
                       gid = "", muid = u""):
    
        self.type = type
        self.dev = dev
        self.qid = qid
        self.mode = mode
        self.atime = atime
        self.mtime = mtime
        self.length = length
        self.name = name
        self.uid = uid
        self.gid = gid
        self.muid = muid
    
    def __repr__(self):
    
        pieces = []
        for name, length in self.format[1:]:
            pieces.append("%s=%s" % (name, repr(self.__dict__[name])))
        
        return "Stat(" + ", ".join(pieces) + ")"
    
    def decode(self, stream = None, data = None):
    
        if stream:
            decode_format(stream, self)
            return self
        else:
            stream = StringReceiver(data)
            items = []
            while stream.ptr < len(data):
                items.append(Stat().decode(stream))
            return items
    
    def encode(self):
    
        args = (self.type, self.dev) + self.qid + (self.mode, self.atime, self.mtime, self.length)
        data = struct.pack("<HIBIQIIIQ", *args)
        data += encode_string(self.name)
        data += encode_string(self.uid)
        data += encode_string(self.gid)
        data += encode_string(self.muid)
        
        # Prepend the size of the fields within the stat structure.
        return encode_data(data)


MessageTypes = {
    Tversion.code: Tversion, 
    Rversion.code: Rversion,
#    Tauth.code: Tauth,
#    Rauth.code: Rauth,
    Tattach.code: Tattach,
    Rattach.code: Rattach,
#    Terror.code: Terror,
    Rerror.code: Rerror,
#    Tflush.code: Tflush,
#    Rflush.code: Rflush,
    Twalk.code: Twalk,
    Rwalk.code: Rwalk,
    Topen.code: Topen,
    Ropen.code: Ropen,
    Tcreate.code: Tcreate,
    Rcreate.code: Rcreate,
    Tread.code: Tread,
    Rread.code: Rread,
    Twrite.code: Twrite,
    Rwrite.code: Rwrite,
    Tclunk.code: Tclunk,
    Rclunk.code: Rclunk,
    Tremove.code: Tremove,
    Rremove.code: Rremove,
    Tstat.code: Tstat,
    Rstat.code: Rstat,
#    Twstat.code: Twstat,
#    Rwstat.code: Rwstat 
    }

def decode(sock = None, data = None):

    if sock:
        stream = SocketReceiver(sock)
    elif data:
        stream = StringReceiver(data)
    else:
        raise StyxError("No valid data to parse.")
    
    # Read the message size (including the size itself), type and tag.
    size = struct.unpack("<I", stream.recv(4))[0]
    message_type = struct.unpack("<b", stream.recv(1))[0]
    tag = struct.unpack("<H", stream.recv(2))[0]
    
    # Find the relevant message class to handle this type and create an
    # instance of it to parse the message data.
    try:
        Message = MessageTypes[message_type]
        return Message().decode(size, tag, stream)
    except:
        #return size, message_type, tag, stream
        raise
