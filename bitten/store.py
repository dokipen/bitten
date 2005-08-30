# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import logging
import os

from trac.core import *
from bitten.util import xmlio

log = logging.getLogger('bitten.store')


class IReportStoreBackend(Interface):

    def store_report(build, step, xml):
        """Store the given report."""

    def retrieve_reports(build, step=None, type=None):
        """Retrieve reports."""


class ReportStore(Component):

    backends = ExtensionPoint(IReportStoreBackend)

    def store_report(self, build, step, xml):
        assert xml.name == 'report' and 'type' in xml.attr
        backend = self._get_configured_backend()
        log.debug('Storing report of type "%s" in %s', xml.attr['type'],
                  backend.__class__.__name__)
        backend.store_report(build, step, xml)

    def query_reports(self, xquery, config=None, build=None, step=None,
                     type=None):
        backend = self._get_configured_backend()
        return backend.query_reports(xquery, config, build, step, type)

    def retrieve_reports(self, build, step=None, type=None):
        backend = self._get_configured_backend()
        return backend.retrieve_reports(build, step, type)

    def _get_configured_backend(self):
        configured = self.config.get('bitten', 'report_store', 'BDBXMLBackend')
        for backend in self.backends:
            if backend.__class__.__name__ == configured:
                return backend
        raise TracError, 'Report store backend not available'


try:
    import dbxml
except ImportError:
    dbxml = None


class BDBXMLBackend(Component):
    implements(IReportStoreBackend)

    indexes = [
        ('config', 'node-metadata-equality-string'),
        ('build', 'node-metadata-equality-decimal'),
        ('step',  'node-metadata-equality-string'),
        ('type',  'node-attribute-equality-string'),
        ('file',  'node-attribute-equality-string'),
        ('line',  'node-attribute-equality-decimal')
    ]


    class XmlValueAdapter(xmlio.ParsedElement):

        def __init__(self, value):
            self._value = value
            self.attr = {}
            for attr in value.getAttributes():
                self.attr[attr.getLocalName()] = attr.getNodeValue()

        name = property(fget=lambda self: self._value.getLocalName())
        namespace = property(fget=lambda self: self._value.getNamespaceURI())

        def children(self, name=None):
            child = self._value.getFirstChild()
            while child:
                if child.isNode() and name in (None, child.getLocalName()):
                    yield BDBXMLBackend.XmlValueAdapter(child)
                child = child.getNextSibling()

        def gettext(self):
            raise NotImplementedError

        def write(self, out, newlines=False):
            return self._value.asString()


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
        doc.setMetaData('', 'config', dbxml.XmlValue(build.config))
        doc.setMetaData('', 'build', dbxml.XmlValue(build.id))
        doc.setMetaData('', 'step', dbxml.XmlValue(step.name))
        container.putDocument(doc, ctxt, dbxml.DBXML_GEN_NAME)

    def query_reports(self, xquery, config=None, build=None, step=None,
                     type=None):
        if dbxml is None:
            log.warning('BDB XML not installed, cannot query reports')
            return
        mgr = dbxml.XmlManager()
        container = self._open_container(mgr)
        ctxt = mgr.createQueryContext()

        constraints = []
        if config:
            constraints.append("dbxml:metadata('config')='%s'" % config.name)
        if build:
            constraints.append("dbxml:metadata('build')=%d" % build.id)
        if step:
            constraints.append("dbxml:metadata('step')='%s'" % step.name)
        if type:
            constraints.append("@type='%s'" % type)

        query = "let $reports := collection('%s')/report" % self.path
        if constraints:
            query += '[%s]' % ' and '.join(constraints)
        query += '\n' + xquery
        self.log.debug('Executíng XQuery: %s', query)

        results = mgr.query(query, ctxt)
        for value in results:
            yield BDBXMLBackend.XmlValueAdapter(value)

    def retrieve_reports(self, build, step=None, type=None):
        if dbxml is None:
            log.warning('BDB XML not installed, cannot retrieve reports')
            return
        return self.query_reports('return $reports', build=build, step=step,
                                  type=type)

    def _open_container(self, mgr, create=False):
        if create and not os.path.exists(self.path):
            container = mgr.createContainer(self.path)
            ctxt = mgr.createUpdateContext()
            for name, index in self.indexes:
                container.addIndex('', name, index, ctxt)
            return container
        return mgr.openContainer(self.path)
