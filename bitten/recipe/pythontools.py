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

import re
from popen2 import Popen3

from bitten import BuildError

def distutils(basedir, command='build'):
    """Execute a `distutils` command."""
    cmdline = 'python setup.py %s' % command
    pipe = Popen3(cmdline, capturestderr=True) # FIXME: Windows compatibility
    while True:
        retval = pipe.poll()
        while True:
            line = pipe.fromchild.readline()
            if not line:
                break
            print '[distutils] %s' % line.rstrip()
        while True:
            line = pipe.childerr.readline()
            if not line:
                break
            print '[distutils] %s' % line.rstrip()
        if retval != -1:
            break
    if retval != 0:
        raise BuildError, "Executing distutils failed (%s)" % retval

def pylint(basedir, file=None):
    """Extract data from a `pylint` run written to a file."""
    assert file, 'Missing required attribute "file"'
    _msg_re = re.compile(r'^(?P<file>.+):(?P<line>\d+): '
                         r'\[(?P<type>[A-Z])(?:, (?P<tag>[\w\.]+))?\] '
                         r'(?P<msg>.*)$')
    for line in open(file, 'r'):
        match = _msg_re.search(line)
        if match:
            filename = match.group('file')
            if filename.startswith(basedir):
                filename = filename[len(basedir) + 1:]
            lineno = int(match.group('line'))
            # TODO: emit to build master

def trace(basedir, summary=None, coverdir=None, include=None, exclude=None):
    """Extract data from a `trac.py` run."""
    assert summary, 'Missing required attribute "summary"'
    assert coverdir, 'Missing required attribute "coverdir"'

def unittest(basedir, file=None):
    """Extract data from a unittest results file in XML format."""
    assert file, 'Missing required attribute "file"'

    from xml.dom import minidom
    root = minidom.parse(open(file, 'r')).documentElement
    assert root.tagName == 'unittest-results'
    for test in root.getElementsByTagName('test'):
        filename = test.getAttribute('file')
        if filename.startswith(basedir):
            filename = filename[len(basedir) + 1:]
        duration = float(test.getAttribute('duration'))
        name = test.getAttribute('name')
        status = test.getAttribute('status')
        # TODO: emit to build master
