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
import tempfile
import shlex
import posixpath
from glob import glob

from bitten.build import CommandLine
from bitten.util import xmlio

log = logging.getLogger('bitten.build.javatools')

def ant(ctxt, file_=None, target=None, keep_going=False, args=None):
    """Run an Ant build."""
    executable = 'ant'
    ant_home = ctxt.config.get_dirpath('ant.home')
    if ant_home:
        executable = os.path.join(ant_home, 'bin', 'ant')

    logfile = tempfile.NamedTemporaryFile(prefix='ant_log', suffix='.xml')
    if args:
        args = shlex.split(args)
    else:
        args = []
    args += ['-noinput', '-listener', 'org.apache.tools.ant.XmlLogger',
             '-Dant.XmlLogger.stylesheet.uri', '""',
             '-DXmlLogger.file', logfile.name]
    if file_:
        args += ['-buildfile', ctxt.resolve(file_)]
    if keep_going:
        args.append('-keep-going')
    if target:
        args.append(target)

    cmdline = CommandLine(executable, args, cwd=ctxt.basedir)
    for out, err in cmdline.execute():
        if out is not None:
            log.info(out)
        if err is not None:
            log.error(err)

    error_logged = False
    log_elem = xmlio.Fragment()
    try:
        xml_log = xmlio.parse(logfile)
        def collect_log_messages(node):
            for child in node.children():
                if child.name == 'message':
                    if child.attr['priority'] == 'debug':
                        continue
                    log_elem.append(xmlio.Element('message',
                                                  level=child.attr['priority'])[
                        child.gettext().replace(ctxt.basedir + os.sep, '')
                                       .replace(ctxt.basedir, '')
                    ])
                else:
                    collect_log_messages(child)
        collect_log_messages(xml_log)

        if 'error' in xml_log.attr:
            ctxt.error(xml_log.attr['error'])
            error_logged = True

    except xmlio.ParseError, e:
        log.warning('Error parsing Ant XML log file (%s)', e)
    ctxt.log(log_elem)

    if not error_logged and cmdline.returncode != 0:
        ctxt.error('Ant failed (%s)' % cmdline.returncode)

def java_src(src, cls):
    return posixpath.join(src, *cls.split('.')) + '.java'

def junit(ctxt, file_=None, src=None):
    assert file_, 'Missing required attribute "file"'
    try:
        total, failed = 0, 0
        results = xmlio.Fragment()
        for f in glob(ctxt.resolve(file_)):
            fd = open(f, 'r')
            try:
                for testcase in xmlio.parse(fd).children('testcase'):
                    test = xmlio.Element('test')
                    test.attr['fixture'] = testcase.attr['classname']
                    test.attr['duration'] = testcase.attr['time']
                    if src:
                        test.attr['file'] = java_src(src,
                                testcase.attr['classname'])

                    result = list(testcase.children())
                    if result:
                        test.attr['status'] = result[0].name
                        test.append(xmlio.Element('traceback')[
                                result[0].gettext()
                            ])
                        failed += 1
                    else:
                        test.attr['status'] = 'success'

                    results.append(test)
                    total += 1
            finally:
                fd.close()
        if failed:
            ctxt.error('%d of %d test%s failed' % (failed, total,
                       total != 1 and 's' or ''))
        ctxt.report('test', results)
    except IOError, e:
        log.warning('Error opening junit results file (%s)', e)
    except xmlio.ParseError, e:
        log.warning('Error parsing junit results file (%s)', e)

