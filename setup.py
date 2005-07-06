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

from distutils.core import setup
from distutils import util
from glob import glob

from bitten import __version__ as VERSION
from bitten.util.testrunner import unittest

scripts = ['scripts/bitten', 'scripts/bittend']
if util.get_platform()[:3] == 'win':
    scripts = [script + '.bat' for script in scripts]

setup(name='bitten', version=VERSION,
      packages=['bitten', 'bitten.build', 'bitten.trac_ext', 'bitten.util'],
      data_files=[('share/bitten/htdocs', glob('htdocs/*.*')),
                  ('share/bitten/templates', glob('templates/*.cs'))],
      scripts=scripts, author="Christopher Lenz", author_email="cmlenz@gmx.de",
      url="http://bitten.cmlenz.net/", cmdclass={'unittest': unittest})
