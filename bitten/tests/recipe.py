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

import os
import tempfile
import unittest

from bitten.recipe import Recipe
from bitten.util import xmlio


class RecipeTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = os.path.realpath(tempfile.gettempdir())

    def test_empty_recipe(self):
        xml = xmlio.parse('<build description="test"/>')
        recipe = Recipe(xml, basedir=self.temp_dir)
        self.assertEqual('test', recipe.description)
        self.assertEqual(self.temp_dir, recipe.ctxt.basedir)
        steps = list(recipe)
        self.assertEqual(0, len(steps))

    def test_single_step(self):
        xml = xmlio.parse('<build>'
                          ' <step id="foo" description="Bar"></step>'
                          '</build>')
        recipe = Recipe(xml, basedir=self.temp_dir)
        steps = list(recipe)
        self.assertEqual(1, len(steps))
        self.assertEqual('foo', steps[0].id)
        self.assertEqual('Bar', steps[0].description)
        self.assertEqual('fail', steps[0].onerror)


def suite():
    return unittest.makeSuite(RecipeTestCase, 'test')

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
