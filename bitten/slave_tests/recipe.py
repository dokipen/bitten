# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import os
import shutil
import tempfile
import unittest

from bitten.build.config import Configuration
from bitten.recipe import Context, Recipe, InvalidRecipeError
from bitten.util import xmlio


class ContextTestCase(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.realpath(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.basedir)

    def test_vars_basedir(self):
        config = Configuration(properties={'foo.bar': 'baz'})
        ctxt = Context('%s/${path}/${foo.bar}' % os.path.realpath('/foo'),
                        config, {'path': 'bar'})

        self.assertEquals(os.path.realpath('/foo/bar/baz'),
                        ctxt.vars['basedir'])

    def test_run_wrong_arg(self):
        ctxt = Context(self.basedir)
        try:
            ctxt.run(1, 'http://bitten.cmlenz.net/tools/sh', 'exec', {'foo':'bar'})
            self.fail("InvalidRecipeError expected")
        except InvalidRecipeError, e:
            self.failUnless("Unsupported argument 'foo'" in str(e))

class RecipeTestCase(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.realpath(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.basedir)

    def test_empty_recipe(self):
        xml = xmlio.parse('<build/>')
        recipe = Recipe(xml, basedir=self.basedir)
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

    def test_validate_bad_root(self):
        xml = xmlio.parse('<foo></foo>')
        recipe = Recipe(xml, basedir=self.basedir)
        self.assertRaises(InvalidRecipeError, recipe.validate)

    def test_validate_no_steps(self):
        xml = xmlio.parse('<build></build>')
        recipe = Recipe(xml, basedir=self.basedir)
        self.assertRaises(InvalidRecipeError, recipe.validate)

    def test_validate_child_not_step(self):
        xml = xmlio.parse('<build><foo/></build>')
        recipe = Recipe(xml, basedir=self.basedir)
        self.assertRaises(InvalidRecipeError, recipe.validate)

    def test_validate_child_not_step(self):
        xml = xmlio.parse('<build><foo/></build>')
        recipe = Recipe(xml, basedir=self.basedir)
        self.assertRaises(InvalidRecipeError, recipe.validate)

    def test_validate_step_without_id(self):
        xml = xmlio.parse('<build><step><cmd/></step></build>')
        recipe = Recipe(xml, basedir=self.basedir)
        self.assertRaises(InvalidRecipeError, recipe.validate)

    def test_validate_step_with_empty_id(self):
        xml = xmlio.parse('<build><step id=""><cmd/></step></build>')
        recipe = Recipe(xml, basedir=self.basedir)
        self.assertRaises(InvalidRecipeError, recipe.validate)

    def test_validate_step_without_commands(self):
        xml = xmlio.parse('<build><step id="test"/></build>')
        recipe = Recipe(xml, basedir=self.basedir)
        self.assertRaises(InvalidRecipeError, recipe.validate)

    def test_validate_step_with_command_children(self):
        xml = xmlio.parse('<build><step id="test">'
                          '<somecmd><child1/><child2/></somecmd>'
                          '</step></build>')
        recipe = Recipe(xml, basedir=self.basedir)
        self.assertRaises(InvalidRecipeError, recipe.validate)

    def test_validate_step_with_duplicate_id(self):
        xml = xmlio.parse('<build>'
                          '<step id="test"><somecmd></somecmd></step>'
                          '<step id="test"><othercmd></othercmd></step>'
                          '</build>')
        recipe = Recipe(xml, basedir=self.basedir)
        self.assertRaises(InvalidRecipeError, recipe.validate)

    def test_validate_successful(self):
        xml = xmlio.parse('<build>'
                          '<step id="foo"><somecmd></somecmd></step>'
                          '<step id="bar"><othercmd></othercmd></step>'
                          '</build>')
        recipe = Recipe(xml, basedir=self.basedir)
        recipe.validate()

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(ContextTestCase, 'test'))
    suite.addTest(unittest.makeSuite(RecipeTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
