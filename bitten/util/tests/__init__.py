# -*- coding: utf-8 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import doctest
import unittest

from bitten.util import xmlio
from bitten.util.tests import beep, md5sum

def suite():
    suite = unittest.TestSuite()
    suite.addTest(beep.suite())
    suite.addTest(md5sum.suite())
    suite.addTest(doctest.DocTestSuite(xmlio))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
