#!/usr/bin/env python

# client.py - A client providing high level methods for accessing a Styx server.
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

import socket
import styx

class ClientError(Exception):
    pass

class Client:

    MSIZE = 16384
    
    def __init__(self, host = None, port = None, uname = None, aname = None):
    
        self.reset()
        
        self.uname = uname
        self.aname = aname
        
        if host != None and port != None:
            self.connect(host, port, uname, aname)
    
    def reset(self):
    
        self.host = None
        self.port = None
        
        self.socket = None
        self.msize = Client.MSIZE
        self.root_fid = 0
        self.current_fid = None
        
        self.replies = {}
    
    def connect(self, host, port, uname, aname):
    
        try:
            s = socket.socket()
            s.connect((host, port))
        except socket.error:
            raise ClientError("Failed to connect to %s:%i." % (host, port))
        
        self.host = host
        self.port = port
        self.socket = s
        
        # Negotiate a version and maximum message size.
        reply = self.send(styx.Tversion(tag=0, msize=self.msize, version=u"9P2000"))
        
        if reply.version != u"9P2000":
            raise ClientError("Server's protocol version '%s' is not supported." % reply.version)
        
        self.msize = min(self.msize, reply.msize)
        
        reply = self.send(styx.Tattach(tag=1, fid=1, afid=0, uname=uname, aname=aname))
        
        self.root_fid = self.current_fid = 1
    
    def disconnect(self):
    
        self.send(styx.Tclunk(tag=2, fid=self.root_fid))
        self.socket.close()
        
        self.reset()
    
    def send(self, msg):
    
        msg.encode(self.socket)
        
        tag = msg.tag
        
        while tag not in self.replies:
        
            reply = styx.decode(sock=self.socket)
            if reply.tag == tag:
                break
            else:
                self.replies[tag] = reply
        else:
            reply = self.replies[tag]
            del self.replies[tag]
        
        if isinstance(reply, styx.Rerror):
        
            if hasattr(msg, "fid"):
                self._clunk_old(msg.fid)
            
            raise ClientError(reply.ename)
        
        return reply
    
    def _clunk(self, fid):
    
        self.send(styx.Tclunk(tag=2, fid=fid))
    
    def _clunk_old(self, fid):
    
        # Clunk the fid only if it is not the root fid.
        if fid != self.root_fid:
            self._clunk(fid)
    
    def _stat(self, fid):
    
        reply = self.send(styx.Tstat(tag=2, fid=fid))
        return reply.stat
    
    def _walk(self, path):
    
        pieces = path.split("/")
        newfid = self._next_fid()
        
        reply = self.send(styx.Twalk(tag=2, fid=self.current_fid,
                                     newfid=newfid, wname=pieces))
        
        if reply.nwqid < len(pieces):
            raise ClientError("No such file or directory: %s" % \
                "/".join(pieces[:reply.nwqid]))
        
        return newfid
    
    def _next_fid(self):
    
        # Alternate between the two integers above the root fid.
        if self.current_fid != self.root_fid:
            return self.current_fid + 1
        else:
            return self.root_fid + 1
    
    def ls(self, path = "", details = False):
    
        newfid = self._walk(path)
        
        # Determine whether the object is a file or directory.
        s = self._stat(newfid)
        
        if s.mode & styx.Stat.DMDIR:
            self.send(styx.Topen(tag=2, fid=newfid, mode=0))
            
            data = ""
            amount = self.msize - 24
            
            while True:
                
                reply = self.send(styx.Tread(
                    tag=2, fid=newfid, offset=len(data), count=amount))
                data += reply.data
                
                if len(reply.data) == 0:
                    break
            
            info = styx.Stat().decode(data=data)
        else:
            # If it is a file then just return the existing information.
            info = [s]
        
        # Release the fid for the file so that it can be reused.
        self._clunk_old(newfid)
        
        if not details:
            info = map(lambda x: (x.name, x.uid, x.gid, x.mode), info)
        
        return info
    
    def cd(self, path):
    
        newfid = self._walk(path)
        
        self._clunk_old(self.current_fid)
        self.current_fid = newfid
    
    def mkdir(self, path, perm):
    
        pieces = path.split("/")
        
        # Walk to the directory regardless of whether it is the current
        # directory because the fid will be reused for the new directory.
        
        if len(pieces) > 1:
            fid = self._walk("/".join(path[:-1]))
            name = path[-1]
        else:
            # Walk to the current directory.
            fid = self._walk("")
            name = path
        
        self.send(styx.Tcreate(tag=2, fid=fid, name=name,
            perm=styx.Stat.DMDIR | perm, mode=0))
        
        # Release the fid so that it can be reused.
        self._clunk_old(fid)
    
    def create(self, path, perm, mode):
    
        pieces = path.split("/")
        
        # Walk to the directory regardless of whether it is the current
        # directory because the fid will be reused for the new file.
        
        if len(pieces) > 1:
            fid = self._walk("/".join(path[:-1]))
            name = path[-1]
        else:
            # Walk to the current directory.
            fid = self._walk("")
            name = path
        
        self.send(styx.Tcreate(tag=2, fid=fid, name=name, perm=perm, mode=mode))
        
        # Release the fid so that it can be reused.
        self._clunk_old(fid)