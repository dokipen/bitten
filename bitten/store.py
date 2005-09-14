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

    def close(self):
        raise NotImplementedError

    def commit(self):
        raise NotImplementedError

    def rollback(self):
        raise NotImplementedError

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

    def close(self):
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

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
    from bsddb3 import db
    import dbxml
except ImportError:
    db = None
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
        self.env = None
        self.mgr = None
        self.container = None
        self.xtn = None

    def _lazyinit(self, create=False):
        if self.container is not None:
            if self.xtn is None:
                self.xtn = self.mgr.createTransaction()
            return True

        exists = os.path.exists(self.path)
        if not exists and not create:
            return False

        self.env = db.DBEnv()
        self.env.open(os.path.dirname(self.path),
                      db.DB_CREATE | db.DB_INIT_LOCK | db.DB_INIT_LOG |
                      db.DB_INIT_MPOOL | db.DB_INIT_TXN, 0)
        self.mgr = dbxml.XmlManager(self.env, 0)
        self.xtn = self.mgr.createTransaction()

        if not exists:
            self.container = self.mgr.createContainer(self.path,
                                                      dbxml.DBXML_TRANSACTIONAL)
            ctxt = self.mgr.createUpdateContext()
            for name, index in self.indices:
                self.container.addIndex(self.xtn, '', name, index, ctxt)
        else:
            self.container = self.mgr.openContainer(self.path,
                                                    dbxml.DBXML_TRANSACTIONAL)

        return True

    def __del__(self):
        self.close()

    def close(self):
        if self.xtn:
            self.xtn.abort()
            self.xtn = None
        if self.container is not None:
            self.container.close()
            self.container = None
        if self.env is not None:
            self.env.close(0)
            self.env = None

    def commit(self):
        if not self.xtn:
            return
        self.xtn.commit()
        self.xtn = None

    def rollback(self):
        if not self.xtn:
            return
        self.xtn.abort()
        self.xtn = None

    def delete(self, config=None, build=None, step=None, type=None):
        if not self._lazyinit(create=False):
            return

        container = self ._open_container()
        if not container:
            return
        ctxt = self.mgr.createUpdateContext()
        for elem in self.query('return $reports', config=config, build=build,
                               step=step, type=type):
            container.deleteDocument(self.xtn, elem._value.asDocument(), ctxt)

    def store(self, build, step, xml):
        assert xml.name == 'report' and 'type' in xml.attr
        assert self._lazyinit(create=True)

        ctxt = self.mgr.createUpdateContext()
        doc = self.mgr.createDocument()
        doc.setContent(str(xml))
        doc.setMetaData('', 'config', dbxml.XmlValue(build.config))
        doc.setMetaData('', 'build', dbxml.XmlValue(build.id))
        doc.setMetaData('', 'step', dbxml.XmlValue(step.name))
        self.container.putDocument(self.xtn, doc, ctxt, dbxml.DBXML_GEN_NAME)

    def query(self, xquery, config=None, build=None, step=None, type=None):
        if not self._lazyinit(create=False):
            return

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
        query += '\n' + (xquery or 'return $reports')

        results = self.mgr.query(self.xtn, query, ctxt, dbxml.DBXML_LAZY_DOCS)
        for value in results:
            yield BDBXMLReportStore.XmlValueAdapter(value)

    def retrieve(self, build, step=None, type=None):
        return self.query('', build=build, step=step, type=type)


def get_store(env):
    if dbxml is None:
        return NullReportStore()
    return BDBXMLReportStore(os.path.join(env.path, 'db', 'bitten.dbxml'))
