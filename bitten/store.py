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

import logging
import os

from trac.core import *

log = logging.getLogger('bitten.store')


class IReportStore(Interface):

    def store_report(build, step, xml):
        """Store the given report."""

    def retrieve_reports(build, step, type=None):
        """Retrieve reports."""


class ReportStore(Component):

    backends = ExtensionPoint(IReportStore)

    def _get_backend(self):
        configured = self.config.get('bitten', 'report_store', 'BDBXMLStore')
        for backend in self.backends:
            if backend.__class__.__name__ == configured:
                return backend
        raise TracError, 'No report store backend available'
    backend = property(fget=lambda self: self._get_backend())

    def store_report(self, build, step, xml):
        assert xml.name == 'report' and 'type' in xml.attr
        self.backend.store_report(build, step, xml)

    def retrieve_reports(self, build, step, type=None):
        return self.backend.retrieve_reports(build, step, type)


try:
    import dbxml
except ImportError:
    dbxml = None


class BDBXMLStore(Component):
    implements(IReportStore)

    indexes = [
        ('build', 'node-metadata-equality-decimal'),
        ('step',  'node-metadata-equality-string'),
        ('type',  'node-attribute-equality-string'),
        ('file',  'node-attribute-equality-string'),
        ('line',  'node-attribute-equality-decimal')
    ]


    class XmlValueWrapper(object):

        _metadata = None

        def __init__(self, value):
            self.value = value

        def __str__(self):
            return self.value.asString()

        def _get_metadata(self):
            if self._metadata is None:
                self._metadata = {}
                for metadata in self.value.asDocument().getMetaDataIterator():
                    if not metadata.get_uri():
                        self._metadata[metadata.get_name()] = \
                            metadata.get_value().asString()
            return self._metadata
        metadata = property(fget=lambda self: self._get_metadata())


    def __init__(self):
        self.path = os.path.join(self.env.path, 'db', 'bitten.dbxml')

    def store_report(self, build, step, xml):
        if dbxml is None:
            log.warning('BDB XML not installed, cannot store report')
            return
        mgr = dbxml.XmlManager()
        container = self._open_container(mgr, create=True)
        ctxt = mgr.createUpdateContext()
        doc = mgr.createDocument()
        doc.setContent(str(xml))
        doc.setMetaData('', 'build', dbxml.XmlValue(build.id))
        doc.setMetaData('', 'step', dbxml.XmlValue(step.name))
        container.putDocument(doc, ctxt, dbxml.DBXML_GEN_NAME)

    def retrieve_reports(self, build, step, type=None):
        if dbxml is None:
            log.warning('BDB XML not installed, cannot retrieve reports')
            return
        path = os.path.join(self.env.path, 'db', 'bitten.dbxml')
        mgr = dbxml.XmlManager()
        container = self._open_container(mgr)
        ctxt = mgr.createQueryContext()
        query = "collection('%s')/report[dbxml:metadata('build')=%d and " \
                                        "dbxml:metadata('step')='%s'" \
                % (path, build.id, step.name)
        if type is not None:
            query += " and @type='%s'" % type
        query += "]"
        results = mgr.query(query, ctxt)
        for value in results:
            yield BDBXMLStore.XmlValueWrapper(value)

    def _open_container(self, mgr, create=False):
        if create and not os.path.exists(self.path):
            container = mgr.createContainer(self.path)
            ctxt = mgr.createUpdateContext()
            for name, index in self.indexes:
                container.addIndex('', name, index, ctxt)
            return container
        return mgr.openContainer(self.path)
