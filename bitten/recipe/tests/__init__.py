import unittest

from bitten.recipe.tests import api

def suite():
    suite = unittest.TestSuite()
    suite.addTest(api.suite())
    return suite
