# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import md5
import os
import shutil
import tempfile
import unittest

from bitten.util import md5sum


class Md5sumTestCase(unittest.TestCase):

    def setUp(self):
        self.tempdir = os.path.realpath(tempfile.mkdtemp(suffix='bitten_test'))

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def _create_file(self, name, content=None):
        filename = os.path.join(self.tempdir, name)
        fd = file(filename, 'w')
        if content:
            fd.write(content)
        fd.close()
        return filename

    def test_generate(self):
        filename = self._create_file('test.xyz', 'Foo bar')
        checksum = md5sum.generate(filename)
        self.assertEqual(md5.new('Foo bar').hexdigest(), checksum)

    def test_write(self):
        filename = self._create_file('test.xyz', 'Foo bar')
        md5file = md5sum.write(filename)
        self.assertEqual(filename + '.md5', md5file)
        fileobj = file(md5file, 'r')
        try:
            checksum, path = fileobj.read().split('  ')
        finally:
            fileobj.close()
        self.assertEqual(md5.new('Foo bar').hexdigest(), checksum)
        self.assertEqual('test.xyz', path)

    def test_write_with_md5file(self):
        filename = self._create_file('test.xyz', 'Foo bar')
        md5file = os.path.join(self.tempdir, 'test.md5')
        self.assertEqual(md5file, md5sum.write(filename, md5file=md5file))
        fileobj = file(md5file, 'r')
        try:
            checksum, path = fileobj.read().split('  ')
        finally:
            fileobj.close()
        self.assertEqual(md5.new('Foo bar').hexdigest(), checksum)
        self.assertEqual('test.xyz', path)

    def test_validate_missing(self):
        filename = self._create_file('test.xyz', 'Foo bar')
        self.assertRaises(md5sum.IntegrityError, md5sum.validate, filename)

    def test_validate_incorrect_digest(self):
        filename = self._create_file('test.xyz', 'Foo bar')
        checksum = md5.new('Foo baz').hexdigest() + '  ' + filename
        md5file = self._create_file('test.xyz.md5', checksum)
        self.assertRaises(md5sum.IntegrityError, md5sum.validate, filename)

    def test_validate_invalid_format(self):
        filename = self._create_file('test.xyz', 'Foo bar')
        checksum = md5.new('Foo bar').hexdigest() + ',' + filename
        md5file = self._create_file('test.xyz.md5', checksum)
        self.assertRaises(md5sum.IntegrityError, md5sum.validate, filename)

    def test_validate_incorrect_path(self):
        filename = self._create_file('test.xyz', 'Foo bar')
        checksum = md5.new('Foo bar').hexdigest() + '  ' + '/etc/test'
        md5file = self._create_file('test.xyz.md5', checksum)
        self.assertRaises(md5sum.IntegrityError, md5sum.validate, filename)

    def test_validate_with_checksum(self):
        filename = self._create_file('test.xyz', 'Foo bar')
        md5sum.validate(filename, md5.new('Foo bar').hexdigest())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(Md5sumTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
