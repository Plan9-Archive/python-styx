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

    @staticmethod
    def parse(sock = None, data = None):
    
        if sock:
            stream = SocketReceiver(sock)
        elif raw_data:
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
        return Message().parse(tag, size, stream)
    
    def decode_string(self, stream):
    
        length = struct.unpack("<H", stream.recv(2))[0]
        return stream.recv(length)
    
    def init(self, tag, size):
    
        self.tag = tag
        self.size = size
    
    def encode_string(self, string):
    
        return struct.pack("<H", len(string)) + string


class Tversion(StyxMessage):

    # size[4] Tversion tag[2] msize[4] version[s]
    
    code = 100
    
    def __init__(self, tag = None, msize = 0, version = ""):
    
        self.tag = tag
        self.msize = msize
        self.version = version
    
    def __repr__(self):
        return "Tversion(tag=%s, msize=%s, version=%s)" % (
            repr(self.tag), repr(self.msize), repr(self.version))
    
    def parse(self, tag, size, stream):
    
        self.init(tag, size)
        self.msize = struct.unpack("<I", stream.recv(4))
        self.version = self.decode_string(stream)
        return self
    
    def write(self, stream):
    
        data = struct.pack("<bHI", self.code, self.tag, self.msize)
        data += self.encode_string(self.version)
        data = struct.pack("<I", len(data) + 4) + data
        stream.sendall(data)


class Rversion(StyxMessage):

    # size[4] Rversion tag[2] msize[4] version[s]
    
    code = 101
    
    def __init__(self, tag = None, msize = 0, version = ""):
    
        self.tag = tag
        self.msize = msize
        self.version = version
    
    def __repr__(self):
        return "Rversion(tag=%s, msize=%s, version=%s)" % (
            repr(self.tag), repr(self.msize), repr(self.version))
    
    def parse(self, tag, size, stream):
    
        self.init(tag, size)
        self.msize = struct.unpack("<I", stream.recv(4))
        self.version = self.decode_string(stream)
        return self
    
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
