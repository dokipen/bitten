# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import os
import shutil
import tempfile
import unittest

from bitten.util import xmlio

class XMLIOTestCase(unittest.TestCase):

    def test_parse(self):
        """Tests that simple test data is parsed correctly"""
        s = """<build xmlns:c="http://bitten.cmlenz.net/tools/c">\n\n  <step id="build" description="Configure and build">\n\n    <c:configure />\n\n  </step>\n\n</build>"""
        x = xmlio.parse(s)
        assert x.name == "build"

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(XMLIOTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
