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
import inspect

from bitten.build import hgtools
from bitten.recipe import Context


class HgPullTestCase(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.realpath(tempfile.mkdtemp())
        self.ctxt = Context(self.basedir)

    def tearDown(self):
        shutil.rmtree(self.basedir)

    def test_command_signature(self):
        self.assertEquals(inspect.getargspec(hgtools.pull),
            (['ctxt', 'revision', 'dir_'], None, None, (None, '.')))

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(HgPullTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
