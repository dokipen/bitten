# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import os
import shutil
import tempfile
import unittest

from bitten.build import FileSet


class FileSetTestCase(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.realpath(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.basedir)

    def test_empty(self):
        fileset = FileSet(self.basedir)
        self.assertRaises(StopIteration, iter(fileset).next)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(FileSetTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
