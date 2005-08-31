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
        self.basedir = os.path.realpath(tempfile.mkdtemp(suffix='bitten_test'))

    def tearDown(self):
        shutil.rmtree(self.basedir)

    # Convenience methods

    def _create_dir(self, *path):
        cur = self.basedir
        for part in path:
            cur = os.path.join(cur, part)
            os.mkdir(cur)
        return cur[len(self.basedir) + 1:]

    def _create_file(self, *path):
        filename = os.path.join(self.basedir, *path)
        fd = file(filename, 'w')
        fd.close()
        return filename[len(self.basedir) + 1:]

    # Test methods

    def test_empty(self):
        fileset = FileSet(self.basedir)
        self.assertRaises(StopIteration, iter(fileset).next)

    def test_top_level_files(self):
        foo_txt = self._create_file('foo.txt')
        bar_txt = self._create_file('bar.txt')
        fileset = FileSet(self.basedir)
        assert foo_txt in fileset and bar_txt in fileset

    def test_files_in_subdir(self):
        self._create_dir('tests')
        foo_txt = self._create_file('tests', 'foo.txt')
        bar_txt = self._create_file('tests', 'bar.txt')
        fileset = FileSet(self.basedir)
        assert foo_txt in fileset and bar_txt in fileset

    def test_files_in_subdir_with_include(self):
        self._create_dir('tests')
        foo_txt = self._create_file('tests', 'foo.txt')
        bar_txt = self._create_file('tests', 'bar.txt')
        fileset = FileSet(self.basedir, include='tests/*.txt')
        assert foo_txt in fileset and bar_txt in fileset

    def test_files_in_subdir_with_exclude(self):
        self._create_dir('tests')
        foo_txt = self._create_file('tests', 'foo.txt')
        bar_txt = self._create_file('tests', 'bar.txt')
        fileset = FileSet(self.basedir, include='tests/*.txt', exclude='bar.*')
        assert foo_txt in fileset and bar_txt not in fileset


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(FileSetTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
