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

import logging
import re

from bitten.build import BuildError
from bitten.util import xmlio
from bitten.util.cmdline import Commandline

log = logging.getLogger('bitten.build.pythontools')

def distutils(ctxt, command='build'):
    """Execute a `distutils` command."""
    cmdline = Commandline('python', ['setup.py', command], cwd=ctxt.basedir)
    log_elem = xmlio.Fragment()
    for out, err in cmdline.execute(timeout=100.0):
        if out:
            log.info(out)
            xmlio.SubElement(log_elem, 'message', level='info')[out]
        if err:
            level = 'error'
            if err.startswith('warning: '):
                err = err[9:]
                level = 'warning'
                log.warning(err)
            else:
                log.error(err)
            xmlio.SubElement(log_elem, 'message', level=level)[err]
    ctxt.log(log_elem)
    if cmdline.returncode != 0:
        raise BuildError, 'distutils failed (%s)' % cmdline.returncode

def pylint(ctxt, file=None):
    """Extract data from a `pylint` run written to a file."""
    assert file, 'Missing required attribute "file"'
    msg_re = re.compile(r'^(?P<file>.+):(?P<line>\d+): '
                         r'\[(?P<type>[A-Z])(?:, (?P<tag>[\w\.]+))?\] '
                         r'(?P<msg>.*)$')
    msg_types = dict(W='warning', E='error', C='convention', R='refactor')

    problems = xmlio.Element('problems')
    try:
        fd = open(ctxt.resolve(file), 'r')
        try:
            for line in fd:
                match = msg_re.search(line)
                if match:
                    type = msg_types.get(match.group('type'))
                    filename = match.group('file')
                    if filename.startswith(ctxt.basedir):
                        filename = filename[len(ctxt.basedir) + 1:]
                    lineno = int(match.group('line'))
                    tag = match.group('tag')
                    xmlio.SubElement(problems, 'problem', type=type, tag=tag,
                                     file=filename, line=lineno)[
                        match.group('msg') or ''
                    ]
            ctxt.report(problems)
        finally:
            fd.close()
    except IOError, e:
        raise BuildError, 'Error opening pylint results file (%s)' % e

def trace(ctxt, summary=None, coverdir=None, include=None, exclude=None):
    """Extract data from a `trace.py` run."""
    assert summary, 'Missing required attribute "summary"'
    assert coverdir, 'Missing required attribute "coverdir"'

def unittest(ctxt, file=None):
    """Extract data from a unittest results file in XML format."""
    assert file, 'Missing required attribute "file"'

    try:
        fd = open(ctxt.resolve(file), 'r')
        try:
            from xml.dom import minidom
            root = minidom.parse(fd).documentElement
            assert root.tagName == 'unittest-results'
            for test in root.getElementsByTagName('test'):
                filename = test.getAttribute('file')
                if filename.startswith(ctxt.basedir):
                    filename = filename[len(ctxt.basedir) + 1:]
                duration = float(test.getAttribute('duration'))
                name = test.getAttribute('name')
                status = test.getAttribute('status')
                # TODO: emit to build master
        finally:
            fd.close()
    except IOError, e:
        raise BuildError, 'Error opening unittest results file (%s)' % e
