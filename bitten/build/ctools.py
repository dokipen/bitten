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

from bitten.util import xmlio
from bitten.util.cmdline import Commandline

log = logging.getLogger('bitten.build.ctools')

def make(ctxt, target=None, file_=None, jobs=None, keep_going=False):
    """Execute a Makefile target."""
    args = ['--directory', ctxt.basedir]
    if file_:
        args += ['--file', ctxt.resolve(file_)]
    if jobs:
        args += ['--jobs', int(jobs)]
    if keep_going:
        args.append('--keep-going')
    if target:
        args.append(target)

    log_elem = xmlio.Fragment()
    cmdline = Commandline('make', args)
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
