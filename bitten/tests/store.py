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
from bitten.store import BDBXMLBackend, FSBackend
from bitten.util import xmlio


class BDBXMLBackendTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = tempfile.mkdtemp('bitten-test')
        os.mkdir(os.path.join(self.env.path, 'db'))

    def tearDown(self):
        shutil.rmtree(self.env.path)

    def test_store_report(self):
        store = BDBXMLBackend(self.env)
        build = Mock(id=42)
        step = Mock(name='foo')
        xml = xmlio.Element('report', type='test')[xmlio.Element('dummy')]
        store.store_report(build, step, xml)

        xml = xmlio.Element('report', type='lint')[xmlio.Element('dummy')]
        store.store_report(build, step, xml)

        reports = list(store.retrieve_reports(build, step))
        self.assertEqual(2, len(reports))
        self.assertEqual('42', reports[0].metadata['build'])
        self.assertEqual('foo', reports[0].metadata['step'])
        self.assertEqual('42', reports[1].metadata['build'])
        self.assertEqual('foo', reports[1].metadata['step'])

        reports = list(store.retrieve_reports(build, step, 'test'))
        self.assertEqual(1, len(reports))

        reports = list(store.retrieve_reports(build, step, 'lint'))
        self.assertEqual(1, len(reports))


class FSBackendTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = tempfile.mkdtemp('bitten-test')

    def tearDown(self):
        shutil.rmtree(self.env.path)

    def test_store_report(self):
        store = FSBackend(self.env)
        build = Mock(id=42)
        step = Mock(name='foo')
        xml = xmlio.Element('report', type='test')[xmlio.Element('dummy')]
        store.store_report(build, step, xml)

        xml = xmlio.Element('report', type='lint')[xmlio.Element('dummy')]
        store.store_report(build, step, xml)

        reports = list(store.retrieve_reports(build, step))
        self.assertEqual(2, len(reports))
        self.assertEqual('42', reports[0].metadata['build'])
        self.assertEqual('foo', reports[0].metadata['step'])
        self.assertEqual('42', reports[1].metadata['build'])
        self.assertEqual('foo', reports[1].metadata['step'])

        reports = list(store.retrieve_reports(build, step, 'test'))
        self.assertEqual(1, len(reports))

        reports = list(store.retrieve_reports(build, step, 'lint'))
        self.assertEqual(1, len(reports))


def suite():
    suite = unittest.TestSuite()
    try:
        import dbxml
        suite.addTest(unittest.makeSuite(BDBXMLBackendTestCase, 'test'))
    except ImportError:
        print>>sys.stderr, 'Skipping unit tests for BDB XML backend'
    suite.addTest(unittest.makeSuite(FSBackendTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
