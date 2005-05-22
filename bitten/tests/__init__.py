import unittest

from bitten.tests import recipe

def suite():
    suite = unittest.TestSuite()
    suite.addTest(recipe.suite())
    return suite
