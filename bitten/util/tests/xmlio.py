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

    def test_ParsedElement_encoding(self):
        u = u'<root foo="øüé€"/>'
        s = '<root foo="\xc3\xb8\xc3\xbc\xc3\xa9\xe2\x82\xac"/>'
        self.assertEquals(u, s.decode('utf-8'))
        # unicode input
        x = xmlio.parse(u)
        out_u = str(x)
        self.assertEquals(out_u, s)
        self.assertEquals(out_u.decode('utf-8'), u)
        # utf-8 input
        x = xmlio.parse(s)
        out_s = str(x)
        self.assertEquals(out_s, s)
        self.assertEquals(out_s.decode('utf-8'), u)
        # identical results
        self.assertEquals(out_u, out_s)

    def test_escape_text(self):
        # unicode
        self.assertEquals(u"Me &amp; you!",
                    xmlio._escape_text(u"Me\x01 & you\x86!"))
        # str
        self.assertEquals("Me &amp; you!",
                    xmlio._escape_text("Me\x01 & you\x86!"))
        # not basestring
        self.assertEquals(42, xmlio._escape_text(42))

    def test_escape_attr(self):
        # unicode
        self.assertEquals(u'&quot;Me &amp; you!&quot;',
                    xmlio._escape_attr(u'"Me\x01 & you\x86!"'))
        # str
        self.assertEquals('&quot;Me &amp; you!&quot;',
                    xmlio._escape_attr('"Me\x01 & you\x86!"'))
        # not basestring
        self.assertEquals(42, xmlio._escape_text(42))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(XMLIOTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
