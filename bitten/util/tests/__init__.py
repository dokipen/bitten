# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import doctest
import unittest

from bitten.util import xmlio as xmlio_module
from bitten.util.tests import xmlio as xmlio_tests

def suite():
    suite = unittest.TestSuite()
    suite.addTest(doctest.DocTestSuite(xmlio_module))
    suite.addTest(xmlio_tests.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
