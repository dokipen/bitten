# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import doctest
import unittest

from bitten.build.tests import pythontools

def suite():
    suite = unittest.TestSuite()
    suite.addTest(pythontools.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
