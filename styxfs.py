#!/usr/bin/env python

# styxfs.py - Simple file server, serving the contents of a directory.
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

import os, shutil, socket, stat, sys
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
            self.clients[client] = FileStore(self.dir)
            
            while client in self.clients:
            
                message = styx.decode(sock=conn)
                print message
                
                try:
                    handler = self.handlers[message.code]
                    reply = handler(self, conn, client, message)
                except KeyError:
                    reply = styx.Rerror(message.tag, "Unsupported message.")
                except StyxFSError, e:
                    reply = styx.Rerror(message.tag, e.message)
                except socket.error:
                    # The connection was probably closed by the client.
                    break
                
                print reply
                reply.encode(conn)
    
    def Tversion(self, conn, client, msg):
    
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
        
        # Generate qids for each of the elements in the path, starting from the
        # path corresponding to the current fid.
        qids = []
        new_path = path.split("/")
        try:
            for element in msg.wname:
            
                if element == "..":
                    # Handle parent directories as path elements.
                    if new_path: new_path.pop()
                else:
                    new_path.append(element)
                
                # Update the qid variable, create qids for each intermediate
                # path, and record the qids created.
                qid = store.make_qid("/".join(new_path))
                qids.append(qid)
        
        except OSError:
            if len(qids) > 0:
                return styx.Rwalk(msg.tag, qids)
            else:
                return styx.Rerror(msg.tag, "Not found.")
        
        # Set the qid and path for the newfid passed by the caller.
        store.set_qid_path(msg.newfid, qid, "/".join(new_path))
        
        return styx.Rwalk(msg.tag, qids)
    
    def Topen(self, conn, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid.
        qid, path = store.get_qid_path(msg.fid)
        
        if not store.open(msg.fid, msg.mode):
            return styx.Rerror(msg.tag, "Cannot open file.")
        
        return styx.Ropen(msg.tag, qid, self.MAX_MSG_SIZE)
    
    def Tcreate(self, conn, client, msg):
    
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
    
    def Tread(self, conn, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid.
        data = store.read(msg.fid, msg.offset, msg.count)
        
        return styx.Rread(msg.tag, data)
    
    def Twrite(self, conn, client, msg):
    
        store = self.clients[client]
        
        # The fid must have an existing qid.
        count = store.write(msg.fid, msg.offset, msg.data)
        
        return styx.Rwrite(msg.tag, count)
    
    def Tclunk(self, conn, client, msg):
    
        store = self.clients[client]
        
        # Release/free the qid.
        store.free_qid_path(msg.fid)
        
        # Additionally, if the fid refers to the root of the file system then
        # remove the client from the clients dictionary to disconnect it.
        if msg.fid == store.root_fid:
            del self.clients[client]
        
        return styx.Rclunk(msg.tag)
    
    def Tremove(self, conn, client, msg):
    
        store = self.clients[client]
        
        # Remove the file and clunk it whether the remove was successful or not.
        result = store.remove(msg.fid)
        
        if result == True:
            store.free_qid_path(msg.fid)
            return styx.Rremove(msg.tag)
        else:
            store.free_qid_path(msg.fid)
            return styx.Rerror(msg.tag, result)
    
    def Tflush(self, conn, client, msg):
    
        store = self.clients[client]
        
        # If we supported a queue of commands then we would remove any pending
        # commands with tags matching msg.oldtag.
        
        return styx.Rflush(msg.tag)
    
    def Twstat(self, conn, client, msg):
    
        store = self.clients[client]
        
        s = store.wstat(msg.fid, msg.stat)
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
        styx.Twstat.code: Twstat
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
        self.opened = {}
        self.root_fid = None
    
    def get_root_qid(self, fid, afid, uname, aname):
    
        qid = self.make_qid("")
        self.set_qid_path(fid, qid, "")
        self.root_fid = fid
        return qid
    
    def get_qid_path(self, fid):
    
        return self.qids[fid], self.paths[fid]
    
    def set_qid_path(self, fid, qid, path):
    
        path = path.lstrip("/")
        
        self.qids[fid] = qid
        self.paths[fid] = path
    
    def make_qid(self, path):
    
        path = path.lstrip("/")
        
        real_path = os.path.join(self.dir, path)
        s = os.stat(real_path)
        if os.path.isdir(real_path):
            qtype = 0x80
        else:
            qtype = 0
        
        qversion = 0
        
        # Use the inode number to uniquely refer to the object at this location.
        qpath = s.st_ino
        
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
    
        path = path.lstrip("/")
        
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
    
    def create(self, fid, name, perm):
    
        if name in (".", ".."):
            return False
        
        elif fid in self.opened:
            return False
        else:
            # Obtain the real path of the directory.
            path = self.paths[fid]
            real_path = os.path.join(self.dir, path)
            
            if not os.path.isdir(real_path):
                return False
            
            # Read the directory permissions.
            dir_perm = os.stat(real_path).st_mode
            
            new_real_path = os.path.join(real_path, name)
            
            if os.path.exists(new_real_path):
                return False
            
            # Create the file or directory with suitable permissions.
            try:
                if perm & styx.Stat.DMDIR:
                    # Only pass the lowest permission bits through to the
                    # underlying filing system.
                    mode = dir_perm & 0777
                    os.mkdir(new_real_path, mode)
                else:
                    mode = dir_perm & 0666
                    os.mknod(new_real_path, mode, stat.S_IFREG)
            
            except OSError:
                return False
            
            # Update the fid to refer to the new object.
            qid = self.make_qid(path + "/" + name)
            self.set_qid_path(fid, qid, path + "/" + name)
        
        return qid
    
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
        real_path = os.path.join(self.dir, path)
        data = ""
        
        if os.path.isdir(real_path):
        
            # Iterate over a sorted list of files in the directory, constructing
            # a byte string of information about them that can be sent in chunks.
            files = os.listdir(real_path)
            files.sort()
            
            for file_name in files:
                qid = self.make_qid(path + "/" + file_name)
                data += self._stat(qid, path + "/" + file_name).encode()
            
            return data[offset:offset + count]
        else:
            f = open(real_path, "rb")
            f.seek(offset)
            data = f.read(count)
            f.close()
            
            return data
    
    def write(self, fid, offset, data):
    
        path = self.paths[fid]
        real_path = os.path.join(self.dir, path)
        
        if os.path.isdir(real_path):
            return styx.Rerror(msg.tag, "Not a file.")
        
        f = open(real_path, "r+wb")
        f.seek(offset)
        f.write(data)
        f.close()
        
        return len(data)
    
    def remove(self, fid):
    
        path = self.paths[fid]
        real_path = os.path.join(self.dir, path)
        
        try:
            if os.path.isdir(real_path):
                os.rmdir(real_path)
            else:
                os.remove(real_path)
        
        except OSError, e:
            return str(e)
        
        return True
    
    def wstat(self, fid, st):
    
        path = self.paths[fid]
        real_path = os.path.join(self.dir, path)
        
        old_name = path.split("/")[-1]
        if st.name != "" and st.name != old_name:
            new_path = os.path.join(os.path.split(real_path)[0], st.name)
            os.rename(real_path, new_path)
            real_path = new_path
        
        s = os.stat(real_path)
        
        if st.mode != 0xffffffff:
            os.chmod(real_path, st.mode & 0777)
        
        if st.mtime != 0xffffffff or st.atime != 0xffffffff:
            if st.mtime == 0xffffffff:
                mtime = s.st_mtime
            else:
                mtime = st.mtime
            
            if st.atime == 0xffffffff:
                atime = s.st_atime
            else:
                atime = st.atime
            
            os.utime(real_path, (atime, mtime))


if __name__ == "__main__":

    if len(sys.argv) != 3:
        sys.stderr.write("Usage: %s <directory> <port>\n" % sys.argv[0])
        sys.exit(1)
    
    directory = sys.argv[1]
    port = int(sys.argv[2])
    
    server = StyxFSServer(directory)
    server.serve("", port)
