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

from bitten.build import ctools
from bitten.recipe import Context, Recipe


class CppUnitTestCase(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.realpath(tempfile.mkdtemp())
        self.ctxt = Context(self.basedir)

    def tearDown(self):
        shutil.rmtree(self.basedir)

    def test_missing_param_file(self):
        self.assertRaises(AssertionError, ctools.cppunit, self.ctxt)

    def test_empty_summary(self):
        cppunit_xml = file(self.ctxt.resolve('cppunit.xml'), 'w')
        cppunit_xml.write("""<?xml version="1.0" encoding='utf-8' ?>
<TestRun>
  <FailedTests>
    <FailedTest id="2">
      <Name>HelloTest::secondTest</Name>
      <FailureType>Assertion</FailureType>
      <Location>
        <File>HelloTest.cxx</File>
        <Line>95</Line>
      </Location>
      <Message>assertion failed
- Expression: 2 == 3
</Message>
    </FailedTest>
  </FailedTests>
  <SuccessfulTests>
    <Test id="1">
      <Name>HelloTest::firstTest</Name>
    </Test>
    <Test id="3">
      <Name>HelloTest::thirdTest</Name>
    </Test>
  </SuccessfulTests>
  <Statistics>
    <Tests>3</Tests>
    <FailuresTotal>1</FailuresTotal>
    <Errors>0</Errors>
    <Failures>1</Failures>
  </Statistics>
</TestRun>""")
        cppunit_xml.close()
        ctools.cppunit(self.ctxt, file_='cppunit.xml')
        type, category, generator, xml = self.ctxt.output.pop()
        self.assertEqual(Recipe.REPORT, type)
        self.assertEqual('test', category)

        tests = list(xml.children)
        self.assertEqual(3, len(tests))
        self.assertEqual('HelloTest', tests[0].attr['fixture'])
        self.assertEqual('secondTest', tests[0].attr['name'])
        self.assertEqual('failure', tests[0].attr['status'])
        self.assertEqual('HelloTest.cxx', tests[0].attr['file'])
        self.assertEqual('95', tests[0].attr['line'])

        self.assertEqual('HelloTest', tests[1].attr['fixture'])
        self.assertEqual('firstTest', tests[1].attr['name'])
        self.assertEqual('success', tests[1].attr['status'])

        self.assertEqual('HelloTest', tests[2].attr['fixture'])
        self.assertEqual('thirdTest', tests[2].attr['name'])
        self.assertEqual('success', tests[2].attr['status'])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(CppUnitTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
