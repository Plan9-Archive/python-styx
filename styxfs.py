#!/usr/bin/env python

import os, socket, stat, sys
import styx

class StyxFSError(Exception):
    pass

class StyxFSServer:

    MAX_MSG_SIZE = 0
    
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
                    reply = handler(self, conn, client, message)
                except KeyError:
                    raise # reply = styx.Rerror(message.tag, "Not connected.")
                except StyxFSError, e:
                    reply = styx.Rerror(message.tag, e.message)
                
                reply.encode(conn)
    
    def Tversion(self, conn, client, msg):
    
        self.clients[client] = FileStore(self.dir)
        
        return styx.Rversion(msg.tag, msg.msize, msg.version)
    
    def Tattach(self, conn, client, msg):
    
        store = self.clients[client]
        
        qid = store.get_root_qid(msg.fid, msg.afid, msg.uname, msg.aname)
        return styx.Rattach(msg.tag, qid)
    
    def Tstat(self, conn, client, msg):
    
        store = self.clients[client]
        
        s = store.stat(msg.fid)
        return styx.Rstat(msg.tag, s)
    
    def Twalk(self, conn, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid but not be in use for open or create.
        qid, path = store.get_qid_path(msg.fid)
        
        # Generate qids for each of the elements in the path.
        qids = []
        try:
            for element in msg.wname:
                path += element
                qid = store.make_qid(path)
                qids.append(qid)
        
        except OSError:
            if len(qids) > 0:
                return styx.Rwalk(msg.tag, qids)
            else:
                return styx.Rerror(msg.tag, "Not found.")
        
        store.set_qid_path(msg.newfid, qid, path)
        
        return styx.Rwalk(msg.tag, qids)
    
    def Topen(self, conn, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid.
        qid, path = store.get_qid_path(msg.fid)
        
        return styx.Ropen(msg.tag, qid, self.MAX_MSG_SIZE)
    
    def Tread(self, conn, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid.
        data = store.read(msg.fid, msg.offset, msg.count)
        
        return styx.Rread(msg.tag, data)
    
    def Tclunk(self, conn, client, msg):
    
        store = self.clients[client]
        
        # Release/free the qid.
        store.free_qid_path(msg.fid)
        
        return styx.Rclunk(msg.tag)
    
    def Rerror(self, conn, msg, message_string):
    
        styx.Rerror(msg.tag, message_string).encode(conn)
    
    handlers = {
        styx.Tversion.code: Tversion,
        styx.Tattach.code: Tattach,
        styx.Tstat.code: Tstat,
        styx.Twalk.code: Twalk,
        styx.Topen.code: Topen,
        styx.Tread.code: Tread,
        styx.Tclunk.code: Tclunk
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
        self.set_qid_path(fid, qid, "")
        return qid
    
    def get_qid_path(self, fid):
    
        return self.qids[fid], self.paths[fid]
    
    def set_qid_path(self, fid, qid, path):
    
        self.qids[fid] = qid
        self.paths[fid] = path
    
    def make_qid(self, path):
    
        path = path.lstrip("/")
        
        file_path = os.path.join(self.dir, path)
        s = os.stat(file_path)
        if os.path.isdir(file_path):
            qtype = 0x80
        else:
            qtype = 0
        
        qversion = 0
        qpath = s.st_ino
        
        return (qtype, qversion, qpath)
    
    def free_qid_path(self, fid):
    
        del self.qids[fid]
        del self.paths[fid]
    
    def stat(self, fid):
    
        qid = self.qids[fid]
        path = self.paths[fid]
        return self._stat(qid, path)
    
    def _stat(self, qid, path):
    
        name = os.path.split(path)[1]
        real_path = os.path.join(self.dir, path)
        s = os.stat(real_path)
        
        if os.path.isdir(real_path):
            mode = 0x80000000
            size = 0
        else:
            mode = 0
            size = s.st_size
        
        mode |= (s.st_mode & 0777)
        
        return styx.Stat(0, 0, qid, mode, s.st_atime, s.st_mtime, size,
                         name, "styxfs", "styxfs", "")
    
    def read(self, fid, offset, count):
    
        path = self.paths[fid]
        real_path = os.path.join(self.dir, path)
        data = ""
        
        if os.path.isdir(real_path):
            files = os.listdir(real_path)
            files.sort()
            
            for file_name in files:
                qid = self.make_qid(path + "/" + file_name)
                data += self._stat(qid, file_name).encode()
            
            return data[offset:offset + count]
        else:
            f = open(real_path, "rb")
            f.seek(offset)
            data = f.read(count)
            f.close()
            
            return data


if __name__ == "__main__":

    if len(sys.argv) != 3:
        sys.stderr.write("Usage: %s <directory> <port>\n" % sys.argv[0])
        sys.exit(1)
    
    directory = sys.argv[1]
    port = int(sys.argv[2])
    
    server = StyxFSServer(directory)
    server.serve("", port)
