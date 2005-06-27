#!/usr/bin/env python
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

import sys

from bitten import BuildError
from bitten.recipe import Recipe

def build():
    step_id = None
    if len(sys.argv) > 1:
        step_id = sys.argv[1]

    recipe = Recipe()
    steps_run = []
    for step in recipe:
        if not step_id or step.id == step_id:
            print '-->', step.description or step.id
            for function, kw in step:
                function(recipe.ctxt, **kw)
            print
            steps_run.append(step.id)

    if step_id and not step_id in steps_run:
        raise BuildError, 'Recipe has no step named "%s"' % step_id

if __name__ == '__main__':
    try:
        build()
    except BuildError, e:
        print>>sys.stderr, 'FAILED: %s' % e
        sys.exit(-1)
    print 'SUCCESS'
