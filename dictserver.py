#!/usr/bin/env python
# -*- encoding: utf8 -*-

# dictserver.py - Serves the contents of a Python dictionary.
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

import sys, time
import styx, styxserver

class DictStore:

    """Maintains information about files and directories beneath the specified
    directory. Information can be accessed by referencing them using
    identifiers.
    """
    
    def __init__(self, dictionary):
    
        self.d = dictionary
        self.qids = {}
        self.paths = {}
        self.opened = {}
        self.root_fid = None
        self.now = int(time.time())
    
    def get_root_qid(self, fid, afid, uname, aname):
    
        qid = self.make_qid(u"/")
        self.set_qid_path(fid, qid, u"/")
        self.root_fid = fid
        return qid
    
    def get_qid_path(self, fid):
    
        return self.qids[fid], self.paths[fid]
    
    def set_qid_path(self, fid, qid, path):
    
        path = path.lstrip(u"/")
        
        self.qids[fid] = qid
        self.paths[fid] = path
    
    def make_qid(self, path):
    
        path = path.lstrip(u"/")
        obj = self.traverse(path)
        
        if obj == None:
            return None
        
        if type(obj) == dict:
            qtype = 0x80
        else:
            qtype = 0
        
        qversion = 0
        
        # Use the id to uniquely refer to the object at this location.
        qpath = id(obj)
        
        return (qtype, qversion, qpath)
    
    def free_qid_path(self, fid):
    
        del self.qids[fid]
        del self.paths[fid]
        
        if fid in self.opened:
            del self.opened[fid]
    
    def stat(self, fid):
    
        qid = self.qids[fid]
        path = self.paths[fid]
        return self._stat(qid, path)
    
    def _stat(self, qid, path):
    
        path = path.lstrip(u"/")
        
        obj = self.traverse(path)
        
        if obj == None:
            return None
        
        if type(obj) == dict:
            mode = 0x80000000
            size = 0
            mode |= 0o555
        else:
            mode = 0
            size = len(obj)
            mode |= 0o444
        
        name = path.split(u"/")[-1]
        
        return styx.Stat(0, 0, qid, mode, self.now, self.now, size, name,
                         u"inferno", u"inferno", u"")
    
    def create(self, fid, name, perm):
        return False
    
    def open(self, fid, mode):
    
        if fid in self.opened:
            self.opened[fid] = mode
            if mode & styx.Stat.DMEXCL:
                return False
        else:
            self.opened[fid] = mode
        
        return True
    
    def is_opened(self, fid):
    
        return fid in self.opened
    
    def read(self, fid, offset, count):
    
        path = self.paths[fid]
        obj = self.traverse(path)
        
        if obj == None:
            return None
        
        data = b""
        
        if type(obj) == dict:
        
            # Iterate over a sorted list of files in the directory, constructing
            # a byte string of information about them that can be sent in chunks.
            files = list(obj.keys())
            files.sort()
            
            for file_name in files:
                qid = self.make_qid(path + u"/" + file_name)
                data += self._stat(qid, path + u"/" + file_name).encode()
            
            return data[offset:offset + count]
        else:
            return obj[offset:offset + count].encode("utf8")
    
    def write(self, fid, offset, data):
    
        # Indicate failure to write any data.
        return -2
    
    def remove(self, fid):
        return u"Cannot remove dictionary entries."
    
    def wstat(self, fid, st):
        pass
    
    def traverse(self, path):
    
        if path == u"":
            return self.d
        
        obj = self.d
        
        for element in path.split(u"/"):
        
            try:
                obj = obj[element]
            except KeyError:
                return None
        
        return obj


if __name__ == "__main__":

    if len(sys.argv) != 2:
        sys.stderr.write("Usage: %s <port>\n" % sys.argv[0])
        sys.exit(1)
    
    port = int(sys.argv[1])
    
    dictionary = {
        u"dir": {
            u"hello.txt": u"Hello world!\n",
            u"\u263a": u"Forståelse"
            }
        }
    
    store = DictStore(dictionary)
    server = styxserver.StyxServer(store)
    server.serve(b"", port)
