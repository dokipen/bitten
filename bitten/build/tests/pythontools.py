# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
#
# Bitten is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Trac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Christopher Lenz <cmlenz@gmx.de>

import os
import os.path
import shutil
import tempfile
import unittest

from bitten.build import pythontools, BuildError
from bitten.recipe import Context, Recipe


class TraceTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.gettempdir()
        self.ctxt = Context(self.temp_dir)
        self.summary = open(os.path.join(self.temp_dir, 'test-coverage.txt'),
                            'w')
        self.coverdir = os.path.join(self.temp_dir, 'coverage')
        os.mkdir(self.coverdir)

    def tearDown(self):
        shutil.rmtree(self.coverdir)
        os.unlink(self.summary.name)

    def test_missing_param_summary(self):
        self.assertRaises(AssertionError, pythontools.trace, self.ctxt,
                          coverdir='coverage')

    def test_missing_param_coverdir(self):
        self.assertRaises(AssertionError, pythontools.trace, self.ctxt,
                          summary='test-coverage.txt')

    def test_empty_summary(self):
        self.summary.write('line  cov%  module  (path)')
        self.summary.close()
        pythontools.trace(self.ctxt, summary=self.summary.name,
                          coverdir=self.coverdir)
        type, function, xml = self.ctxt.output.pop()
        self.assertEqual(Recipe.REPORT, type)
        self.assertEqual(0, len(xml.children))



class UnittestTestCase(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.gettempdir()
        self.ctxt = Context(self.temp_dir)
        self.results_xml = open(os.path.join(self.temp_dir, 'test-results.xml'),
                                'w')

    def tearDown(self):
        os.unlink(os.path.join(self.temp_dir, 'test-results.xml'))

    def test_missing_file_param(self):
        self.assertRaises(AssertionError, pythontools.unittest, self.ctxt)

    def test_invalid_file_param(self):
        self.assertRaises(BuildError,
                          pythontools.unittest, self.ctxt, file='foobar')

    def test_empty_results(self):
        self.results_xml.write('<?xml version="1.0"?>'
                              '<unittest-results>'
                              '</unittest-results>')
        self.results_xml.close()
        pythontools.unittest(self.ctxt, self.results_xml.name)
        type, function, xml = self.ctxt.output.pop()
        self.assertEqual(Recipe.REPORT, type)
        self.assertEqual(0, len(xml.children))

    def test_successful_test(self):
        self.results_xml.write('<?xml version="1.0"?>'
                              '<unittest-results>'
                              '<test duration="0.12" status="success"'
                              '      file="bar_test.py"'
                              '      name="test_foo (pkg.BarTestCase)"/>'
                              '</unittest-results>')
        self.results_xml.close()
        pythontools.unittest(self.ctxt, self.results_xml.name)
        type, function, xml = self.ctxt.output.pop()
        self.assertEqual(Recipe.REPORT, type)
        self.assertEqual(1, len(xml.children))
        test_elem = xml.children[0]
        self.assertEqual('test', test_elem.name)
        self.assertEqual('0.12', test_elem.attr['duration'])
        self.assertEqual('success', test_elem.attr['status'])
        self.assertEqual('bar_test.py', test_elem.attr['file'])
        self.assertEqual('test_foo (pkg.BarTestCase)', test_elem.attr['name'])

    def test_file_path_normalization(self):
        self.results_xml.write('<?xml version="1.0"?>'
                              '<unittest-results>'
                              '<test duration="0.12" status="success"'
                              '      file="%s"'
                              '      name="test_foo (pkg.BarTestCase)"/>'
                              '</unittest-results>'
                              % os.path.join(self.ctxt.basedir, 'bar_test.py'))
        self.results_xml.close()
        pythontools.unittest(self.ctxt, self.results_xml.name)
        type, function, xml = self.ctxt.output.pop()
        self.assertEqual('bar_test.py', xml.children[0].attr['file'])

    def test_missing_file_attribute(self):
        self.results_xml.write('<?xml version="1.0"?>'
                              '<unittest-results>'
                              '<test duration="0.12" status="success"'
                              '      name="test_foo (pkg.BarTestCase)"/>'
                              '</unittest-results>')
        self.results_xml.close()
        pythontools.unittest(self.ctxt, self.results_xml.name)
        type, function, xml = self.ctxt.output.pop()
        self.assertEqual(None, xml.children[0].attr.get('file'))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TraceTestCase, 'test'))
    suite.addTest(unittest.makeSuite(UnittestTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
