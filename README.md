Python Styx module and servers
==============================

This repository contains a collection of Python modules and scripts that can be
used to implement basic Styx/9P2000 file servers. I found it useful to create
these in order to learn about the protocol, and have made them available so
that others can experiment with them.

The `styx.py` file is a module that contains classes describing messages used
in the protocol and functions that can encode and decode messages.

The `styxserver.py` file is a module that provides a server class that operates
on a data store object that is supplied to it when it is instantiated.

The `localfileserver.py` script implements an example data store that serves
the contents of a local directory. The `dictserver.py` script shows how to
provide a data store that serves the contents of a Python dictionary.

The `client.py` module provides a class that lets Python programs perform a few
high level operations on files and directories.

License
-------

The contents of this package are licensed under the GNU General Public License
(version 3 or later):

 Copyright (C) 2018 David Boddie <david@boddie.org.uk>

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
