# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import unittest

from bitten.build.tests import api, config, ctools, pythontools, xmltools

def suite():
    suite = unittest.TestSuite()
    suite.addTest(api.suite())
    suite.addTest(config.suite())
    suite.addTest(ctools.suite())
    suite.addTest(pythontools.suite())
    suite.addTest(xmltools.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
