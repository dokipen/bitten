# -*- coding: utf-8 -*-
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
import zipfile

from trac.test import Mock
from bitten.slave import BuildSlave


class BuildSlaveTestCase(unittest.TestCase):

    def setUp(self):
        self.work_dir = tempfile.mkdtemp(prefix='bitten_test')
        self.slave = Slave(None, work_dir=self.work_dir)
        self.handler = OrchestrationProfileHandler(Mock(session=self.slave))

    def tearDown(self):
        shutil.rmtree(self.work_dir)

    def _create_file(self, *path):
        filename = os.path.join(self.work_dir, *path)
        fd = file(filename, 'w')
        fd.close()
        return filename


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(BuildSlaveTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
