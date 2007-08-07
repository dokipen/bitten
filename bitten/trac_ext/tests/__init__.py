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

from bitten.trac_ext.tests import charts, web_ui

def suite():
    suite = unittest.TestSuite()
    suite.addTest(charts.suite())
    suite.addTest(web_ui.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
