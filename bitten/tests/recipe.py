# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import os
import shutil
import tempfile
import unittest

from bitten.recipe import Recipe
from bitten.util import xmlio


class RecipeTestCase(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.realpath(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.basedir)

    def test_empty_recipe(self):
        xml = xmlio.parse('<build description="test"/>')
        recipe = Recipe(xml, basedir=self.basedir)
        self.assertEqual('test', recipe.description)
        self.assertEqual(self.basedir, recipe.ctxt.basedir)
        steps = list(recipe)
        self.assertEqual(0, len(steps))

    def test_empty_step(self):
        xml = xmlio.parse('<build>'
                          ' <step id="foo" description="Bar"></step>'
                          '</build>')
        recipe = Recipe(xml, basedir=self.basedir)
        steps = list(recipe)
        self.assertEqual(1, len(steps))
        self.assertEqual('foo', steps[0].id)
        self.assertEqual('Bar', steps[0].description)
        self.assertEqual('fail', steps[0].onerror)


def suite():
    return unittest.makeSuite(RecipeTestCase, 'test')

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
