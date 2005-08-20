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
import os
import re
import shlex

from bitten.recipe import Recipe
from bitten.util import xmlio
from bitten.util.cmdline import Commandline

log = logging.getLogger('bitten.build.pythontools')

def distutils(ctxt, command='build'):
    """Execute a `distutils` command."""
    cmdline = Commandline('python', ['setup.py', command], cwd=ctxt.basedir)
    log_elem = xmlio.Fragment()
    for out, err in cmdline.execute():
        if out is not None:
            if out:
                log.info(out)
            xmlio.SubElement(log_elem, 'message', level='info')[out]
        if err is not None:
            level = 'error'
            if err.startswith('warning: '):
                err = err[9:]
                level = 'warning'
                log.warning(err)
            else:
                log.error(err)
            if err:
                xmlio.SubElement(log_elem, 'message', level=level)[err]
    ctxt.log(log_elem)
    if cmdline.returncode != 0:
        ctxt.error('distutils failed (%s)' % cmdline.returncode)

def exec_(ctxt, file_=None, module=None, output=None, args=None):
    """Execute a python script."""
    assert file_ or module, 'Either "file" or "module" attribute required'

    if module:
        # Script specified as module name, need to resolve that to a file
        mod = __import__(module, globals(), locals(), [])
        components = module.split('.')
        for comp in components[1:]:
            mod = getattr(mod, comp)
        file_ = mod.__file__

    if args:
        args = shlex.split(args)
    else:
        args = []

    output_file = None
    if output:
        output = ctxt.resolve(output)
        output_file = file(output, 'w')

    try:
        cmdline = Commandline('python', [file_] + args, cwd=ctxt.basedir)
        log_elem = xmlio.Fragment()
        for out, err in cmdline.execute():
            if out is not None:
                log.info(out)
                if output_file:
                    output_file.write(out + os.linesep)
                if out:
                    xmlio.SubElement(log_elem, 'message', level='info')[out]
            if err is not None:
                level = 'error'
                if err.startswith('warning: '):
                    err = err[9:]
                    level = 'warning'
                    log.warning(err)
                else:
                    log.error(err)
                if output_file:
                    output_file.write(err + os.linesep)
                if err:
                    xmlio.SubElement(log_elem, 'message', level=level)[err]
        ctxt.log(log_elem)
    finally:
        if output_file:
            output_file.close()

    if cmdline.returncode != 0:
        ctxt.error('distutils failed (%s)' % cmdline.returncode)

def pylint(ctxt, file_=None):
    """Extract data from a `pylint` run written to a file."""
    assert file_, 'Missing required attribute "file"'
    msg_re = re.compile(r'^(?P<file>.+):(?P<line>\d+): '
                        r'\[(?P<type>[A-Z]\d*)(?:, (?P<tag>[\w\.]+))?\] '
                        r'(?P<msg>.*)$')
    msg_categories = dict(W='warning', E='error', C='convention', R='refactor')

    problems = xmlio.Element('problems')
    try:
        fd = open(ctxt.resolve(file_), 'r')
        try:
            for line in fd:
                match = msg_re.search(line)
                if match:
                    msg_type = match.group('type')
                    category = msg_categories.get(msg_type[0])
                    if len(msg_type) == 1:
                        msg_type = None
                    filename = os.path.realpath(match.group('file'))
                    if filename.startswith(ctxt.basedir):
                        filename = filename[len(ctxt.basedir) + 1:]
                    lineno = int(match.group('line'))
                    tag = match.group('tag')
                    xmlio.SubElement(problems, 'problem', category=category,
                                     type=msg_type, tag=tag, file=filename,
                                     line=lineno)[match.group('msg') or '']
            ctxt.report(problems)
        finally:
            fd.close()
    except IOError, e:
        log.warning('Error opening pylint results file (%s)', e)

def trace(ctxt, summary=None, coverdir=None, include=None, exclude=None):
    """Extract data from a `trace.py` run."""
    assert summary, 'Missing required attribute "summary"'
    assert coverdir, 'Missing required attribute "coverdir"'

    summary_line_re = re.compile(r'^\s*(?P<lines>\d+)\s+(?P<cov>\d+)%\s+'
                                 r'(?P<module>.*?)\s+\((?P<filename>.*?)\)')
    coverage_line_re = re.compile(r'\s*(?:(?P<hits>\d+): )?(?P<line>.*)')

    try:
        summary_file = open(ctxt.resolve(summary), 'r')
        try:
            coverage = xmlio.Fragment()
            for summary_line in summary_file:
                match = summary_line_re.search(summary_line)
                if match:
                    filename = os.path.realpath(match.group(4))
                    modname = match.group(3)
                    cov = int(match.group(2))
                    if filename.startswith(ctxt.basedir):
                        filename = filename[len(ctxt.basedir) + 1:]
                        module = xmlio.Element('coverage', file=filename,
                                               module=modname, percentage=cov)
                        coverage_path = ctxt.resolve(coverdir,
                                                     modname + '.cover')
                        if not os.path.exists(coverage_path):
                            log.warning('No coverage file for module %s at %s',
                                        modname, coverage_path)
                            continue
                        coverage_file = open(coverage_path, 'r')
                        try:
                            for num, coverage_line in enumerate(coverage_file):
                                match = coverage_line_re.search(coverage_line)
                                if match:
                                    hits = match.group(1)
                                    if hits:
                                        line = xmlio.Element('line', line=num,
                                                             hits=int(hits))
                                        module.append(line)
                        finally:
                            coverage_file.close()
                        coverage.append(module)
            ctxt.report(coverage)
        finally:
            summary_file.close()
    except IOError, e:
        log.warning('Error opening coverage summary file (%s)', e)

def unittest(ctxt, file_=None):
    """Extract data from a unittest results file in XML format."""
    assert file_, 'Missing required attribute "file"'

    try:
        fd = open(ctxt.resolve(file_), 'r')
        try:
            results = xmlio.Fragment()
            for child in xmlio.parse(fd).children():
                test = xmlio.Element('test')
                for name, value in child.attr.items():
                    if name == 'file':
                        value = os.path.realpath(value)
                        if value.startswith(ctxt.basedir):
                            value = value[len(ctxt.basedir) + 1:]
                        else:
                            continue
                    test.attr[name] = value
                for grandchild in child.children():
                    test.append(grandchild)
                results.append(test)
            ctxt.report(results)
        finally:
            fd.close()
    except IOError, e:
        log.warning('Error opening unittest results file (%s)', e)
    except xmlio.ParseError, e:
        log.warning('Error parsing unittest results file (%s)', e)
