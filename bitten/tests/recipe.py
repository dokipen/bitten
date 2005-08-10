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
import os.path
import tempfile
import unittest

from bitten.recipe import Recipe


class RecipeTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.gettempdir()
        self.recipe_xml = open(os.path.join(self.temp_dir, 'recipe.xml'), 'w')

    def tearDown(self):
        self.recipe_xml.close()
        os.unlink(os.path.join(self.temp_dir, 'recipe.xml'))

    def test_empty_recipe(self):
        self.recipe_xml.write('<?xml version="1.0"?>'
                              '<build description="test">'
                              '</build>')
        self.recipe_xml.close()
        recipe = Recipe(basedir=self.temp_dir)
        self.assertEqual('test', recipe.description)
        self.assertEqual(self.temp_dir, recipe.ctxt.basedir)
        steps = list(recipe)
        self.assertEqual(0, len(steps))

    def test_single_step(self):
        self.recipe_xml.write('<?xml version="1.0"?>'
                              '<build>'
                              ' <step id="foo" description="Bar"></step>'
                              '</build>')
        self.recipe_xml.close()
        recipe = Recipe(basedir=self.temp_dir)
        steps = list(recipe)
        self.assertEqual(1, len(steps))
        self.assertEqual('foo', steps[0].id)
        self.assertEqual('Bar', steps[0].description)
        self.assertEqual('fail', steps[0].onerror)


def suite():
    return unittest.makeSuite(RecipeTestCase, 'test')

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
