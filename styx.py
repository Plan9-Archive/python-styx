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

# Using the information from the Inferno man 5 0intro page.

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


class StyxMessage:

    def decode_string(self, stream):
    
        length = struct.unpack("<H", stream.recv(2))[0]
        return stream.recv(length).decode("utf8")
    
    def init(self, size, tag):
    
        self.size = size
        self.tag = tag
    
    def encode_string(self, string):
    
        utf8 = string.encode("utf8")
        return struct.pack("<H", len(utf8)) + utf8
    
    def _parse_format(self, stream):
    
        self.fields = {
            "size": repr(self.size),
            "tag": repr(self.tag)
            }
        
        for piece in self.format.split()[3:]:
        
            begin = piece.find("[")
            
            if begin != -1:
            
                name = piece[:begin]
                end = piece.find("]", begin)
                length = piece[begin + 1:end]
                
                if length == "s":
                    # UTF-8 string
                    value = self.decode_string(stream)
                elif length == "n":
                    # n bytes of raw data
                    n = struct.unpack("<H", stream.recv(2))
                    value = stream.recv(n)
                elif length == "2":
                    value = struct.unpack("<H", stream.recv(2))
                elif length == "4":
                    value = struct.unpack("<I", stream.recv(4))
                else:
                    raise
                
                self.fields[name] = repr(value)
                self.__dict__[name] = value
    
    def parse(self, size, tag, stream):
    
        self.init(size, tag)
        self._parse_format(stream)
        return self
    
    def __repr__(self):
    
        return self.repr_format % self.fields


class Tversion(StyxMessage):

    code = 100
    format = "size[4] Tversion tag[2] msize[4] version[s]"
    repr_format = "Tversion(tag=%(tag)s, msize=%(msize)s, version=%(version)s)"
    
    def __init__(self, tag = None, msize = 0, version = ""):
    
        self.tag = tag
        self.msize = msize
        self.version = version
    
    def write(self, stream):
    
        data = struct.pack("<bHI", self.code, self.tag, self.msize)
        data += self.encode_string(self.version)
        data = struct.pack("<I", len(data) + 4) + data
        stream.sendall(data)


class Rversion(StyxMessage):

    code = 101
    format = "size[4] Rversion tag[2] msize[4] version[s]"
    repr_format = "Rversion(tag=%(tag)s, msize=%(msize)s, version=%(version)s)"
    
    def __init__(self, tag = None, msize = 0, version = ""):
    
        self.tag = tag
        self.msize = msize
        self.version = version
    
    def write(self, stream):
    
        data = struct.pack("<bHI", self.code, self.tag, self.msize)
        data += self.encode_string(self.version)
        data = struct.pack("<I", len(data) + 4) + data
        stream.sendall(data)



MessageTypes = {
    Tversion.code: Tversion, 
    Rversion.code: Rversion,
#    Tauth.code: Tauth,
#    Rauth.code: Rauth,
#    Tattach.code: Tattach,
#    Rattach.code: Rattach,
#    Terror.code: Terror,
#    Rerror.code: Rerror,
#    Tflush.code: Tflush,
#    Rflush.code: Rflush,
#    Twalk.code: Twalk,
#    Rwalk.code: Rwalk,
#    Topen.code: Topen,
#    Ropen.code: Ropen,
#    Tcreate.code: Tcreate,
#    Rcreate.code: Rcreate,
#    Tread.code: Tread,
#    Rread.code: Rread,
#    Twrite.code: Twrite,
#    Rwrite.code: Rwrite,
#    Tclunk.code: Tclunk,
#    Rclunk.code: Rclunk,
#    Tremove.code: Tremove,
#    Rremove.code: Rremove,
#    Tstat.code: Tstat,
#    Rstat.code: Rstat,
#    Twstat.code: Twstat,
#    Rwstat.code: Rwstat 
    }


def parse(sock = None, data = None):

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
    Message = MessageTypes[message_type]
    return Message().parse(size, tag, stream)
