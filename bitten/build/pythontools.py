# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import logging
import os
import re
try:
    set
except NameError:
    from sets import Set as set
import sys

from bitten.build import CommandLine, FileSet
from bitten.util import loc, xmlio

log = logging.getLogger('bitten.build.pythontools')

def _python_path(ctxt):
    """Return the path to the Python interpreter.
    
    If the configuration has a `python.path` property, the value of that option
    is returned; otherwise the path to the current Python interpreter is
    returned.
    """
    python_path = ctxt.config.get_filepath('python.path')
    if python_path:
        return python_path
    return sys.executable

def distutils(ctxt, command='build', file_='setup.py'):
    """Execute a `distutils` command."""
    cmdline = CommandLine(_python_path(ctxt), [ctxt.resolve(file_), command],
                          cwd=ctxt.basedir)
    log_elem = xmlio.Fragment()
    for out, err in cmdline.execute():
        if out is not None:
            log.info(out)
            log_elem.append(xmlio.Element('message', level='info')[out])
        if err is not None:
            level = 'error'
            if err.startswith('warning: '):
                err = err[9:]
                level = 'warning'
                log.warning(err)
            else:
                log.error(err)
            log_elem.append(xmlio.Element('message', level=level)[err])
    ctxt.log(log_elem)
    if cmdline.returncode != 0:
        ctxt.error('distutils failed (%s)' % cmdline.returncode)

def exec_(ctxt, file_=None, module=None, function=None, output=None, args=None):
    """Execute a python script."""
    assert file_ or module, 'Either "file" or "module" attribute required'
    if function:
        assert module and not file_, '"module" attribute required for use of ' \
                                     '"function" attribute'

    if module:
        # Script specified as module name, need to resolve that to a file,
        # or use the function name if provided
        if function:
            args = '-c "import sys; from %s import %s; %s(sys.argv)" %s' % (
                   module, function, function, args)
        else:
            try:
                mod = __import__(module, globals(), locals(), [])
                components = module.split('.')
                for comp in components[1:]:
                    mod = getattr(mod, comp)
                file_ = mod.__file__.replace('\\', '/')
            except ImportError, e:
                ctxt.error('Cannot execute Python module %s: %s' % (module, e))
                return

    from bitten.build import shtools
    shtools.exec_(ctxt, executable=_python_path(ctxt), file_=file_,
                  output=output, args=args)

def pylint(ctxt, file_=None):
    """Extract data from a `pylint` run written to a file."""
    assert file_, 'Missing required attribute "file"'
    msg_re = re.compile(r'^(?P<file>.+):(?P<line>\d+): '
                        r'\[(?P<type>[A-Z]\d*)(?:, (?P<tag>[\w\.]+))?\] '
                        r'(?P<msg>.*)$')
    msg_categories = dict(W='warning', E='error', C='convention', R='refactor')

    problems = xmlio.Fragment()
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
                    filename = filename.replace(os.sep, '/')
                    lineno = int(match.group('line'))
                    tag = match.group('tag')
                    problems.append(xmlio.Element('problem', category=category,
                                                  type=msg_type, tag=tag,
                                                  line=lineno, file=filename)[
                        match.group('msg') or ''
                    ])
            ctxt.report('lint', problems)
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

    fileset = FileSet(ctxt.basedir, include, exclude)
    missing_files = []
    for filename in fileset:
        if os.path.splitext(filename)[1] != '.py':
            continue
        missing_files.append(filename)
    covered_modules = set()

    try:
        summary_file = open(ctxt.resolve(summary), 'r')
        try:
            coverage = xmlio.Fragment()
            for summary_line in summary_file:
                match = summary_line_re.search(summary_line)
                if match:
                    modname = match.group(3)
                    filename = match.group(4)
                    if not os.path.isabs(filename):
                        filename = os.path.normpath(os.path.join(ctxt.basedir,
                                                                 filename))
                    else:
                        filename = os.path.realpath(filename)
                    if not filename.startswith(ctxt.basedir):
                        continue
                    filename = filename[len(ctxt.basedir) + 1:]
                    if not filename in fileset:
                        continue

                    missing_files.remove(filename)
                    covered_modules.add(modname)
                    module = xmlio.Element('coverage', name=modname,
                                           file=filename.replace(os.sep, '/'),
                                           percentage=int(match.group(2)))
                    coverage_path = ctxt.resolve(coverdir, modname + '.cover')
                    if os.path.exists(coverage_path):
                        coverage_file = open(coverage_path, 'r')
                        lines = []
                        try:
                            for coverage_line in coverage_file:
                                match = coverage_line_re.search(coverage_line)
                                if match:
                                    hits = match.group(1)
                                    if hits:
                                        lines.append(hits)
                                    else:
                                        lines.append('0')
                        finally:
                            coverage_file.close()
                        module.attr['lines'] = len(lines)
                        module.append(xmlio.Element('line_hits')[
                            ' '.join(lines)
                        ])
                    else:
                        log.warning('No coverage file for module %s at %s',
                                    modname, coverage_path)

                        # Estimate total number of lines from covered lines and
                        # percentage
                        lines = int(match.group(1))
                        percentage = int(match.group(2))
                        module.attr['lines'] = lines * 100 / percentage
                    coverage.append(module)

            for filename in missing_files:
                modname = os.path.splitext(filename.replace(os.sep, '.'))[0]
                if modname in covered_modules:
                    continue
                covered_modules.add(modname)
                module = xmlio.Element('coverage', name=modname,
                                       file=filename.replace(os.sep, '/'),
                                       percentage=0)
                filepath = ctxt.resolve(filename)
                fileobj = file(filepath, 'r')
                try:
                    lines = 0
                    for lineno, linetype, line in loc.count(fileobj):
                        if linetype == loc.CODE:
                            lines += 1
                    module.attr['lines'] = lines
                finally:
                    fileobj.close()
                coverage.append(module)

            ctxt.report('coverage', coverage)
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
                            value = value.replace(os.sep, '/')
                        else:
                            continue
                    test.attr[name] = value
                for grandchild in child.children():
                    test.append(xmlio.Element(grandchild.name)[
                        grandchild.gettext()
                    ])
                results.append(test)
            ctxt.report('test', results)
        finally:
            fd.close()
    except IOError, e:
        log.warning('Error opening unittest results file (%s)', e)
    except xmlio.ParseError, e:
        log.warning('Error parsing unittest results file (%s)', e)
