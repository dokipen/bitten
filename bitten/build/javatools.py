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

from bitten.build import CommandLine
from bitten.util import xmlio

log = logging.getLogger('bitten.build.javatools')

def ant(ctxt, file_=None, target=None, keep_going=False):
    """Run an Ant build."""
    executable = 'ant'
    ant_home = ctxt.config.get_dirpath('ant.home')
    if ant_home:
        executable = os.path.join(ant_home, 'bin', 'ant')

    logfile = tempfile.NamedTemporaryFile(prefix='ant_log', suffix='.xml')
    args = ['-noinput', '-listener', 'org.apache.tools.ant.XmlLogger',
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
    except xmlio.ParseError, e:
        log.warning('Error parsing Ant XML log file (%s)', e)
    ctxt.log(log_elem)

    if cmdline.returncode != 0:
        ctxt.error('Ant failed (%s)' % cmdline.returncode)
