# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
#
# Bitten is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Trac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Christopher Lenz <cmlenz@gmx.de>

from popen2 import Popen3

def make(basedir, target='all'):
    """Execute a Makefile target."""
    cmdline = 'make %s' % target
    pipe = Popen3(cmdline, capturestderr=True) # FIXME: Windows compatibility
    while True:
        retval = pipe.poll()
        if retval != -1:
            break
        line = pipe.fromchild.readline()
        if line:
            print '[make] %s' % line.rstrip()
        line = pipe.childerr.readline()
        if line:
            print '[make] %s' % line.rstrip()
    if retval != 0:
        raise BuildError, "Executing distutils failed (%s)" % retval
