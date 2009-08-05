# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import unittest
from bitten.slave_tests import recipe, slave
from bitten.build import tests as build
from bitten.util import tests as util

def suite():
    suite = unittest.TestSuite()
    suite.addTest(recipe.suite())
    suite.addTest(slave.suite())
    suite.addTest(build.suite())
    suite.addTest(util.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
