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
import sys
import tempfile
import unittest

from trac.test import EnvironmentStub, Mock
from bitten.store import BDBXMLBackend
from bitten.util import xmlio


class BDBXMLBackendTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = tempfile.mkdtemp('bitten-test')
        os.mkdir(os.path.join(self.env.path, 'db'))
        self.store = BDBXMLBackend(self.env)

    def tearDown(self):
        shutil.rmtree(self.env.path)

    def test_store_report(self):
        """
        Verify that storing a single report in the database works as expected.
        """
        build = Mock(id=42, config='trunk')
        step = Mock(name='foo')
        xml = xmlio.Element('report', type='test')[xmlio.Element('dummy')]
        self.store.store_report(build, step, xml)

        self.assertEqual(1, len(list(self.store.retrieve_reports(build, step,
                                                                 'test'))))

    def test_retrieve_reports_for_step(self):
        """
        Verify that all reports for a build step are retrieved if the report
        type parameter is omitted.
        """
        build = Mock(id=42, config='trunk')
        step = Mock(name='foo')
        xml = xmlio.Element('report', type='test')[xmlio.Element('dummy')]
        self.store.store_report(build, step, xml)
        xml = xmlio.Element('report', type='lint')[xmlio.Element('dummy')]
        self.store.store_report(build, step, xml)

        other_step = Mock(name='bar')
        xml = xmlio.Element('report', type='test')[xmlio.Element('dummy')]
        self.store.store_report(build, other_step, xml)

        self.assertEqual(2, len(list(self.store.retrieve_reports(build, step))))

    def test_retrieve_reports_for_build(self):
        """
        Verify that all reports for a build are retrieved if the build step and
        report type parameters are omitted.
        """
        build = Mock(id=42, config='trunk')
        step_foo = Mock(name='foo')
        step_bar = Mock(name='bar')
        xml = xmlio.Element('report', type='test')[xmlio.Element('dummy')]
        self.store.store_report(build, step_foo, xml)
        xml = xmlio.Element('report', type='lint')[xmlio.Element('dummy')]
        self.store.store_report(build, step_bar, xml)

        other_build = Mock(id=66, config='trunk')
        step_baz = Mock(name='foo')
        xml = xmlio.Element('report', type='test')[xmlio.Element('dummy')]
        self.store.store_report(other_build, step_baz, xml)

        self.assertEqual(2, len(list(self.store.retrieve_reports(build))))


def suite():
    suite = unittest.TestSuite()
    try:
        import dbxml
        suite.addTest(unittest.makeSuite(BDBXMLBackendTestCase, 'test'))
    except ImportError:
        print>>sys.stderr, 'Skipping unit tests for BDB XML backend'
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
