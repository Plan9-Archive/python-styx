# styxserver.py - Network code for handling Styx (9P2000) messages.
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

class StyxServerError(Exception):
    pass

class StyxServer:

    MAX_MSG_SIZE = 0
    
    def __init__(self, store):
    
        self.store = store
        self.clients = {}
    
    def serve(self, host, port):
    
        s = socket.socket()
        s.bind((host, port))
        s.listen(1)
        
        while True:
        
            conn, client = s.accept()
            self.clients[client] = self.store
            
            while client in self.clients:
            
                message = styx.decode(sock=conn)
                
                try:
                    handler = self.handlers[message.code]
                    reply = handler(self, client, message)
                except KeyError:
                    reply = styx.Rerror(message.tag, "Unsupported message.")
                except StyxServerError as e:
                    reply = styx.Rerror(message.tag, e.message)
                except socket.error:
                    # The connection was probably closed by the client.
                    break
                
                reply.encode(conn)
    
    def Tversion(self, client, msg):
    
        return styx.Rversion(msg.tag, msg.msize, msg.version)
    
    def Tattach(self, client, msg):
    
        store = self.clients[client]
        
        qid = store.get_root_qid(msg.fid, msg.afid, msg.uname, msg.aname)
        if qid == None:
            return styx.Rerror(msg.tag, "Root not found.")
        
        return styx.Rattach(msg.tag, qid)
    
    def Tstat(self, client, msg):
    
        store = self.clients[client]
        
        s = store.stat(msg.fid)
        if s == None:
            return styx.Rerror(msg.tag, "Not found.")
        
        return styx.Rstat(msg.tag, s)
    
    def Twalk(self, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid but not be in use for open or create.
        qid, path = store.get_qid_path(msg.fid)
        
        # Generate qids for each of the elements in the path, starting from the
        # path corresponding to the current fid.
        qids = []
        new_path = path.split("/")
        
        for element in msg.wname:
        
            if element == "..":
                # Handle parent directories as path elements.
                if new_path: new_path.pop()
            else:
                new_path.append(element)
            
            # Update the qid variable, create qids for each intermediate
            # path, and record the qids created.
            qid = store.make_qid("/".join(new_path))
            
            if qid == None:
                if len(qids) > 0:
                    return styx.Rwalk(msg.tag, qids)
                else:
                    return styx.Rerror(msg.tag, "Not found.")
            
            qids.append(qid)
        
        # Set the qid and path for the newfid passed by the caller.
        store.set_qid_path(msg.newfid, qid, "/".join(new_path))
        
        return styx.Rwalk(msg.tag, qids)
    
    def Topen(self, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid.
        qid, path = store.get_qid_path(msg.fid)
        
        if not store.open(msg.fid, msg.mode):
            return styx.Rerror(msg.tag, "Cannot open file.")
        
        return styx.Ropen(msg.tag, qid, self.MAX_MSG_SIZE)
    
    def Tcreate(self, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid that corresponds to a directory
        # and cannot be itself in use.
        qid, path = store.get_qid_path(msg.fid)
        
        new_qid = store.create(msg.fid, msg.name, msg.perm)
        if new_qid == False:
            return styx.Rerror(msg.tag, "Cannot create file.")
        
        # The fid now refers to the newly open file or directory.
        if not store.open(msg.fid, msg.mode):
            return styx.Rerror(msg.tag, "Cannot open file.")
        
        return styx.Rcreate(msg.tag, new_qid, self.MAX_MSG_SIZE)
    
    def Tread(self, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid.
        data = store.read(msg.fid, msg.offset, msg.count)
        
        return styx.Rread(msg.tag, data)
    
    def Twrite(self, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid.
        count = store.write(msg.fid, msg.offset, msg.data)
        
        if count == -1:
            return styx.Rerror(msg.tag, "Not a file.")
        elif count != len(msg.data):
            return styx.Rerror(msg.tag, "Failed to write data.")
        
        return styx.Rwrite(msg.tag, count)
    
    def Tclunk(self, client, msg):
    
        store = self.clients[client]
        
        # Release/free the qid.
        store.free_qid_path(msg.fid)
        
        # Additionally, if the fid refers to the root of the file system then
        # remove the client from the clients dictionary to disconnect it.
        if msg.fid == store.root_fid:
            del self.clients[client]
        
        return styx.Rclunk(msg.tag)
    
    def Tremove(self, client, msg):
    
        store = self.clients[client]
        
        # Remove the file and clunk it whether the remove was successful or not.
        result = store.remove(msg.fid)
        
        if result == True:
            store.free_qid_path(msg.fid)
            return styx.Rremove(msg.tag)
        else:
            store.free_qid_path(msg.fid)
            return styx.Rerror(msg.tag, result)
    
    def Tflush(self, client, msg):
    
        store = self.clients[client]
        
        # If we supported a queue of commands then we would remove any pending
        # commands with tags matching msg.oldtag.
        
        return styx.Rflush(msg.tag)
    
    def Twstat(self, client, msg):
    
        store = self.clients[client]
        
        store.wstat(msg.fid, msg.stat)
        return styx.Rwstat(msg.tag)
    
    handlers = {
        styx.Tversion.code: Tversion,
        styx.Tattach.code: Tattach,
        styx.Tstat.code: Tstat,
        styx.Twalk.code: Twalk,
        styx.Topen.code: Topen,
        styx.Tcreate.code: Tcreate,
        styx.Tread.code: Tread,
        styx.Twrite.code: Twrite,
        styx.Tclunk.code: Tclunk,
        styx.Tremove.code: Tremove,
        styx.Twstat.code: Twstat,
        styx.Tflush.code: Tflush
        }
