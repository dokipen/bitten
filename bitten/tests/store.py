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


def suite():
    try:
        import dbxml
        return unittest.makeSuite(BDBXMLBackendTestCase, 'test')
    except ImportError:
        print>>sys.stderr, 'Skipping unit tests for BDB XML backend'
    return unittest.TestSuite()
