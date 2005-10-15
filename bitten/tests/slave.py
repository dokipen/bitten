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
import zipfile

from trac.test import Mock
from bitten.slave import Slave, OrchestrationProfileHandler
from bitten.util import beep


class OrchestrationProfileHandlerTestCase(unittest.TestCase):

    def setUp(self):
        self.work_dir = tempfile.mkdtemp(prefix='bitten_test')
        self.slave = Slave(None, None)
        self.handler = OrchestrationProfileHandler(Mock(session=self.slave))

    def tearDown(self):
        shutil.rmtree(self.work_dir)

    def _create_file(self, *path):
        filename = os.path.join(self.work_dir, *path)
        fd = file(filename, 'w')
        fd.close()
        return filename

    def test_unpack_invalid_zip_1(self):
        """
        Verify handling of `IOError` exceptions when trying to unpack an
        invalid ZIP file.

        The `zipfile` module will actually raise an `IOError` instead of a
        `zipfile.error` here because it'll try to seek past the beginning of
        the file.
        """
        path = self._create_file('invalid.zip')
        zip = file(path, 'w')
        zip.write('INVALID')
        zip.close()
        self.assertRaises(beep.ProtocolError, self.handler.unpack_snapshot, 0,
                          os.path.dirname(path), 'invalid.zip')

    def test_unpack_invalid_zip_2(self):
        """
        Verify handling of `zip.error` exceptions when trying to unpack an
        invalid ZIP file.
        """
        path = self._create_file('invalid.zip')
        zip = file(path, 'w')
        zip.write('INVALIDINVALIDINVALIDINVALIDINVALIDINVALID')
        zip.close()
        self.assertRaises(beep.ProtocolError, self.handler.unpack_snapshot, 0,
                          os.path.dirname(path), 'invalid.zip')

def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(OrchestrationProfileHandlerTestCase,
                                     'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
