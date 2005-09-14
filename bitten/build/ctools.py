# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import logging

from bitten.build import CommandLine
from bitten.util import xmlio

log = logging.getLogger('bitten.build.ctools')

def make(ctxt, target=None, file_=None, keep_going=False):
    """Execute a Makefile target."""
    args = ['--directory', ctxt.basedir]
    if file_:
        args += ['--file', ctxt.resolve(file_)]
    if keep_going:
        args.append('--keep-going')
    if target:
        args.append(target)

    log_elem = xmlio.Fragment()
    cmdline = CommandLine('make', args)
    for out, err in cmdline.execute():
        if out is not None:
            log.info(out)
            xmlio.SubElement(log_elem, 'message', level='info')[out]
        if err is not None:
            log.error(err)
            xmlio.SubElement(log_elem, 'message', level='error')[err]
    ctxt.log(log_elem)

    if cmdline.returncode != 0:
        ctxt.error('make failed (%s)' % cmdline.returncode)
