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

from bitten.build import BuildError
from bitten.util.cmdline import Commandline

def make(ctxt, target='all', file=None, jobs=None, keep_going=False):
    """Execute a Makefile target."""
    args = ['-C', ctxt.basedir]
    if file:
        args += ['-f', ctxt.resolve(file)]
    if jobs:
        args += ['-j', int(jobs)]
    if keep_going:
        args.append('-k')
    args.append(target)
    cmdline = Commandline('make', args)
    for out, err in cmdline.execute(timeout=100.0):
        if out:
            for line in out.splitlines():
                print '[make] %s' % line
        if err:
            for line in err.splitlines():
                print '[make] %s' % err
    if cmdline.returncode != 0:
        raise BuildError, "Executing make failed (%s)" % cmdline.returncode
