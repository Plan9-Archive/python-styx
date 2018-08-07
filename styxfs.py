#!/usr/bin/env python

import os, socket, stat, sys
import styx

class StyxFSError(Exception):
    pass

class StyxFSServer:

    def __init__(self, directory):
    
        self.dir = directory
        self.clients = {}
    
    def serve(self, host, port):
    
        s = socket.socket()
        s.bind((host, port))
        s.listen(1)
        
        while True:
        
            conn, client = s.accept()
            
            while True:
                message = styx.decode(sock=conn)
                
                try:
                    handler = self.handlers[message.code]
                    handler(self, conn, client, message)
                except KeyError:
                    self.Rerror(conn, message, "Not connected.")
                except StyxFSError, e:
                    self.Rerror(conn, message, e.message)
    
    def Tversion(self, conn, client, msg):
    
        self.clients[client] = FileStore(self.dir)
        
        reply = styx.Rversion(msg.tag, msg.msize, msg.version)
        reply.encode(conn)
    
    def Tattach(self, conn, client, msg):
    
        store = self.clients[client]
        
        qid = store.get_root_qid(msg.fid, msg.afid, msg.uname, msg.aname)
        reply = styx.Rattach(msg.tag, qid)
        reply.encode(conn)
    
    def Tstat(self, conn, client, msg):
    
        store = self.clients[client]
        
        s = store.stat(msg.fid)
        reply = styx.Rstat(msg.tag, s)
        reply.encode(conn)
    
    def Twalk(self, conn, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid.
        qid = store.get_qid(msg.fid)
        path = store.get_path(msg.fid)
        
        # Generate qids for each of the elements in the path.
        qids = []
        for element in msg.wname:
            path += element
            store.make_qid(fid, path)
            qids.append(store.get_qid(fid))
        
        s = store.stat(msg.fid)
        
        # The newfid must not have an existing qid. We use the newfid to
        # register the qid for the last path element.
        store.get_qid(msg.newfid)
        
        reply = styx.Rstat(msg.tag, s)
        reply.encode(conn)
    
    def Rerror(self, conn, msg, message_string):
    
        styx.Rerror(msg.tag, message_string).encode(conn)
    
    handlers = {
        styx.Tversion.code: Tversion,
        styx.Tattach.code: Tattach,
        styx.Tstat.code: Tstat,
        styx.Twalk.code: Twalk
        }


class FileStore:

    """Maintains information about files and directories beneath the specified
    directory. Information can be accessed by referencing them using
    identifiers.
    """
    
    def __init__(self, directory):
    
        self.dir = os.path.abspath(directory)
        self.qids = {}
        self.paths = {}
    
    def get_root_qid(self, fid, afid, uname, aname):
    
        qid = self.make_qid("")
        self.qids[fid] = qid
        self.paths[fid] = ""
        return qid
    
    def get_qid(self, fid):
    
        return self.qids[fid]
    
    def get_path(self, fid):
    
        return self.paths[fid]
    
    def make_qid(self, path):
    
        path.lstrip("/")
        
        file_path = os.path.join(self.dir, path)
        s = os.stat(file_path)
        if os.path.isdir(file_path):
            qtype = 0x80
        else:
            qtype = 0
        
        qversion = 0
        qpath = s.st_ino
        
        return (qtype, qversion, qpath)
    
    def stat(self, fid):
    
        qid = self.qids[fid]
        file_path = self.paths[fid]
        
        real_path = os.path.join(self.dir, file_path)
        s = os.stat(real_path)
        
        if os.path.isdir(real_path):
            mode = 0x80000000
            size = 0
        else:
            mode = 0
            size = s.st_size
        
        mode |= (s.st_mode & 0777)
        
        return styx.Stat(0, 0, qid, mode, s.st_atime, s.st_mtime, size,
                         os.getenv("USER", "inferno"), "styxfs", "styxfs", "")


if __name__ == "__main__":

    if len(sys.argv) != 3:
        sys.stderr.write("Usage: %s <directory> <port>\n" % sys.argv[0])
        sys.exit(1)
    
    directory = sys.argv[1]
    port = int(sys.argv[2])
    
    server = StyxFSServer(directory)
    server.serve("", port)
