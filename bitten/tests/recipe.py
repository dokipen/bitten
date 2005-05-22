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
        os.unlink(os.path.join(self.temp_dir, 'recipe.xml'))

    def testDescription(self):
        self.recipe_xml.write('<?xml version="1.0"?>'
                              '<recipe description="test">'
                              '</recipe>')
        self.recipe_xml.close()
        recipe = Recipe(basedir=self.temp_dir)
        self.assertEqual('test', recipe.description)

def suite():
    return unittest.makeSuite(RecipeTestCase, 'test')
