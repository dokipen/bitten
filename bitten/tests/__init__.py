# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import unittest

from bitten.tests import model, recipe, queue
from bitten.build import tests as build
from bitten.util import tests as util
from bitten.trac_ext import tests as trac_ext

def suite():
    suite = unittest.TestSuite()
    suite.addTest(model.suite())
    suite.addTest(recipe.suite())
    suite.addTest(queue.suite())
    suite.addTest(build.suite())
    suite.addTest(trac_ext.suite())
    suite.addTest(util.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
