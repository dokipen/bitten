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


class ReportStore(object):

    def delete(self, config=None, build=None, step=None, type=None):
        raise NotImplementedError

    def query(self, xquery, config=None, build=None, step=None,
                     type=None):
        raise NotImplementedError

    def retrieve(self, build, step=None, type=None):
        raise NotImplementedError

    def store(self, build, step, xml):
        raise NotImplementedError


class NullReportStore(ReportStore):

    def delete(self, config=None, build=None, step=None, type=None):
        return

    def query(self, xquery, config=None, build=None, step=None,
                     type=None):
        return []

    def retrieve(self, build, step=None, type=None):
        return []

    def store(self, build, step, xml):
        return


try:
    import dbxml
except ImportError:
    dbxml = None


class BDBXMLReportStore(ReportStore):

    indices = [
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
                elif child.isNull():
                    break
                child = child.getNextSibling()

        def gettext(self):
            text = []
            child = self._value.getFirstChild()
            while child:
                if child.isNode() and child.getNodeName() == '#text':
                    text.append(child.getNodeValue())
                elif child.isNull():
                    break
                child = child.getNextSibling()
            return ''.join(text)

        def write(self, out, newlines=False):
            return self._value.asString()


    def __init__(self, path):
        self.path = path
        self.mgr = dbxml.XmlManager()
        if not os.path.exists(path):
            self.container = self.mgr.createContainer(self.path)
            ctxt = self.mgr.createUpdateContext()
            for name, index in self.indices:
                self.container.addIndex('', name, index, ctxt)
        else:
            self.container = self.mgr.openContainer(self.path)

    def delete(self, config=None, build=None, step=None, type=None):
        ctxt = self.mgr.createUpdateContext()
        for elem in self.query('return $reports', config=config, build=build,
                               step=step, type=type):
            self.container.deleteDocument(elem._value.asDocument(), ctxt)

    def store(self, build, step, xml):
        assert xml.name == 'report' and 'type' in xml.attr
        ctxt = self.mgr.createUpdateContext()
        doc = self.mgr.createDocument()
        doc.setContent(str(xml))
        doc.setMetaData('', 'config', dbxml.XmlValue(build.config))
        doc.setMetaData('', 'build', dbxml.XmlValue(build.id))
        doc.setMetaData('', 'step', dbxml.XmlValue(step.name))
        self.container.putDocument(doc, ctxt, dbxml.DBXML_GEN_NAME)

    def query(self, xquery, config=None, build=None, step=None,
                     type=None):
        ctxt = self.mgr.createQueryContext()

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

        results = self.mgr.query(query, ctxt)
        for value in results:
            yield BDBXMLReportStore.XmlValueAdapter(value)

    def retrieve(self, build, step=None, type=None):
        return self.query('return $reports', build=build, step=step, type=type)


def get_store(env):
    if dbxml is None:
        return NullReportStore()
    return BDBXMLReportStore(os.path.join(env.path, 'db', 'bitten.dbxml'))
