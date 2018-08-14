#!/usr/bin/env python

# localfileserver.py - Simple file server, serving the contents of a directory.
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

import locale, os, stat, sys
import styx, styxserver

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
        self.encoding = sys.getfilesystemencoding()
    
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
        
        real_path = os.path.join(self.dir, path).encode(self.encoding)
        
        try:
            s = os.stat(real_path)
            
            if os.path.isdir(real_path):
                qtype = 0x80
            else:
                qtype = 0
        
        except OSError:
            return None
        
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
    
        path = path.lstrip(u"/")
        
        name = os.path.split(path)[1]
        real_path = os.path.join(self.dir, path).encode(self.encoding)
        
        try:
            s = os.stat(real_path)
        except OSError:
            return None
        
        if os.path.isdir(real_path):
            mode = 0x80000000
            size = 0
        else:
            mode = 0
            size = s.st_size
        
        mode |= (s.st_mode & 0o777)
        
        return styx.Stat(0, 0, qid, mode, s.st_atime, s.st_mtime, size,
                         name, u"styxfs", u"styxfs", u"")
    
    def create(self, fid, name, perm):
    
        if name in (u".", u".."):
            return False
        
        elif fid in self.opened:
            return False
        else:
            # Obtain the real path of the directory.
            path = self.paths[fid]
            real_path = os.path.join(self.dir, path).encode(self.encoding)
            
            if not os.path.isdir(real_path):
                return False
            
            # Read the directory permissions.
            dir_perm = os.stat(real_path).st_mode
            
            new_real_path = os.path.join(self.dir, path, name).encode(self.encoding)
            
            if os.path.exists(new_real_path):
                return False
            
            # Create the file or directory with suitable permissions.
            try:
                if perm & styx.Stat.DMDIR:
                    # Only pass the lowest permission bits through to the
                    # underlying filing system.
                    mode = dir_perm & 0o777
                    os.mkdir(new_real_path, mode)
                else:
                    mode = dir_perm & 0o666
                    os.mknod(new_real_path, mode, stat.S_IFREG)
            
            except OSError:
                return False
            
            # Update the fid to refer to the new object.
            qid = self.make_qid(path + u"/" + name)
            self.set_qid_path(fid, qid, path + u"/" + name)
        
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
        data = b""
        
        if os.path.isdir(real_path):
        
            # Iterate over a sorted list of files in the directory, constructing
            # a byte string of information about them that can be sent in chunks.
            files = os.listdir(real_path)
            files.sort()
            
            for file_name in files:
                qid = self.make_qid(path + u"/" + file_name)
                data += self._stat(qid, path + u"/" + file_name).encode()
            
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
            return -1
        
        f = open(real_path, "r+b")
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
        
        except OSError as e:
            return str(e)
        
        return True
    
    def wstat(self, fid, st):
    
        path = self.paths[fid]
        real_path = os.path.join(self.dir, path).encode(self.encoding)
        
        pieces = path.split(u"/")
        old_name = pieces[-1]
        
        # Only update the name if the specified name is not empty and differs
        # from the existing path.
        if st.name != u"" and st.name != old_name:
            # Rename the file and use the new path for any further operations.
            new_path = os.path.join(os.path.split(real_path)[0], st.name).encode(self.encoding)
            os.rename(real_path, new_path)
            real_path = new_path
            # Update the path dictionary to contain the new path.
            self.paths[fid] = pieces + [u"/" + st.name]
        
        s = os.stat(real_path)
        
        if st.mode != 0xffffffff:
            os.chmod(real_path, st.mode & 0o777)
        
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
    
    store = FileStore(directory)
    server = styxserver.StyxServer(store)
    server.serve(b"", port)
