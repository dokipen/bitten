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

import itertools
import logging
import sys

from bitten.build import BuildError
from bitten.recipe import Recipe
from bitten.util import xmlio

def main():
    from bitten import __version__ as VERSION
    from optparse import OptionParser

    parser = OptionParser(usage='usage: %prog [options] [step1] [step2] ...',
                          version='%%prog %s' % VERSION)
    parser.add_option('-f', '--recipe-file', action='store', dest='recipe_file',
                      metavar='FILE', help='read build recipe from FILE')
    parser.add_option('--print-reports', action='store_const',
                      dest='print_reports', const=True,
                      help='print generated reports')
    parser.add_option('-v', '--verbose', action='store_const', dest='loglevel',
                      const=logging.DEBUG, help='print as much as possible')
    parser.add_option('-q', '--quiet', action='store_const', dest='loglevel',
                      const=logging.ERROR, help='print as little as possible')
    parser.set_defaults(loglevel=logging.INFO, recipe_file='recipe.xml')
    options, args = parser.parse_args()

    log = logging.getLogger('bitten')
    log.setLevel(options.loglevel)
    handler = logging.StreamHandler()
    handler.setLevel(options.loglevel)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler)

    steps_to_run = dict([(step, False) for step in args])

    recipe_file = file(options.recipe_file, 'r')
    try:
        recipe = Recipe(xmlio.parse(recipe_file))
        for step in recipe:
            if not steps_to_run or step.id in steps_to_run:
                print
                print '-->', step.id
                for type, function, output in step.execute(recipe.ctxt):
                    if type == Recipe.ERROR:
                        log.error('Failure in step "%s": %s', step.id, output)
                    elif type == Recipe.REPORT and options.print_reports:
                        output.write(sys.stdout, newlines=True)
                if step.id in steps_to_run:
                    steps_to_run[step.id] = True
    finally:
        recipe_file.close()

if __name__ == '__main__':
    try:
        main()
    except BuildError, e:
        print
        print>>sys.stderr, 'FAILED: %s' % e
        sys.exit(-1)
    print
    print 'SUCCESS'
