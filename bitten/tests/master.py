# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import os
import re
import shutil
from StringIO import StringIO
import tempfile
import unittest
from Cookie import SimpleCookie as Cookie

from trac.db import DatabaseManager
from trac.perm import PermissionCache, PermissionSystem
from trac.test import EnvironmentStub, Mock
from trac.util.datefmt import to_datetime, utc
from trac.web.api import RequestDone
from trac.web.href import Href

from bitten.master import BuildMaster
from bitten.model import BuildConfig, TargetPlatform, Build, BuildStep, \
                         BuildLog, Report, schema
from bitten.slave import PROTOCOL_VERSION

class BuildMasterTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub(enable=['trac.*', 'bitten.*'])
        self.env.path = tempfile.mkdtemp()
        logs_dir = self.env.config.get("bitten", "logs_dir")
        if os.path.isabs(logs_dir):
            raise ValueError("Should not have absolute logs directory for temporary test")
        logs_dir = os.path.join(self.env.path, logs_dir)
        os.makedirs(logs_dir)

        PermissionSystem(self.env).grant_permission('hal', 'BUILD_EXEC')

        # Create tables
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        connector, _ = DatabaseManager(self.env)._get_connector()
        for table in schema:
            for stmt in connector.to_sql(table):
                cursor.execute(stmt)

        self.repos = Mock(get_changeset=lambda rev: Mock(author = 'author'))
        self.env.get_repository = lambda authname=None: self.repos

    def tearDown(self):
        shutil.rmtree(self.env.path)

    def test_create_build(self):
        BuildConfig(self.env, 'test', path='somepath', active=True).insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('family', 'posix'))
        platform.insert()

        self.repos = Mock(
            get_node=lambda path, rev=None: Mock(
                get_entries=lambda: [Mock(), Mock()],
                get_history=lambda: [('somepath', 123, 'edit'),
                                     ('somepath', 121, 'edit'),
                                     ('somepath', 120, 'edit')]
            ),
            get_changeset=lambda rev: Mock(date=to_datetime(42, utc)),
            normalize_path=lambda path: path,
            rev_older_than=lambda rev1, rev2: rev1 < rev2
        )

        inheaders = {'Content-Type': 'application/x-bitten+xml'}
        inbody = StringIO("""<slave name="hal" version="%d">
  <platform>Power Macintosh</platform>
  <os family="posix" version="8.1.0">Darwin</os>
  <package name="java" version="2.4.3"/>
</slave>""" % PROTOCOL_VERSION)
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='', path_info='/builds',
                   href=Href('/trac'), abs_href=Href('http://example.org/trac'),
                   remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   get_header=lambda x: inheaders.get(x), read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(201, outheaders['Status'])
        self.assertEqual('text/plain', outheaders['Content-Type'])
        location = outheaders['Location']
        mo = re.match('http://example.org/trac/builds/(\d+)', location)
        assert mo, 'Location was %r' % location
        self.assertEqual('Build pending', outbody.getvalue())
        build = Build.fetch(self.env, int(mo.group(1)))
        self.assertEqual(Build.IN_PROGRESS, build.status)
        self.assertEqual('hal', build.slave)

    def test_create_build_invalid_xml(self):
        inheaders = {'Content-Type': 'application/x-bitten+xml'}
        inbody = StringIO('<slave></salve>')
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='', path_info='/builds',
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   get_header=lambda x: inheaders.get(x), read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEquals(400, outheaders['Status'])
        self.assertEqual('XML parser error', outbody.getvalue())

    def test_create_build_no_post(self):
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='GET', base_path='', path_info='/builds',
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEquals(405, outheaders['Status'])
        self.assertEquals('Only POST allowed for build creation',
                    outbody.getvalue())

    def test_create_build_no_match(self):
        inheaders = {'Content-Type': 'application/x-bitten+xml'}
        inbody = StringIO("""<slave name="hal" version="%d">
  <platform>Power Macintosh</platform>
  <os family="posix" version="8.1.0">Darwin</os>
</slave>""" % PROTOCOL_VERSION)
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='', path_info='/builds',
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   get_header=lambda x: inheaders.get(x), read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(204, outheaders['Status'])
        self.assertEqual('', outbody.getvalue())

    def test_create_build_protocol_wrong_version(self):
        inheaders = {'Content-Type': 'application/x-bitten+xml'}
        inbody = StringIO("""<slave name="hal" version="%d">
  <platform>Power Macintosh</platform>
  <os family="posix" version="8.1.0">Darwin</os>
</slave>""" % (PROTOCOL_VERSION-1,))
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='', path_info='/builds',
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   get_header=lambda x: inheaders.get(x), read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(400, outheaders['Status'])
        self.assertEqual('Master-Slave version mismatch: master=%d, slave=%d' \
                                % (PROTOCOL_VERSION, PROTOCOL_VERSION-1),
                            outbody.getvalue())

    def test_create_build_protocol_no_version(self):
        inheaders = {'Content-Type': 'application/x-bitten+xml'}
        inbody = StringIO("""<slave name="hal">
  <platform>Power Macintosh</platform>
  <os family="posix" version="8.1.0">Darwin</os>
</slave>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='', path_info='/builds',
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   get_header=lambda x: inheaders.get(x), read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(400, outheaders['Status'])
        self.assertEqual('Master-Slave version mismatch: master=%d, slave=1' \
                                % (PROTOCOL_VERSION,),
                            outbody.getvalue())

    def test_cancel_build(self):
        config = BuildConfig(self.env, 'test', path='somepath', active=True,
                             recipe='<build></build>')
        config.insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      status=Build.IN_PROGRESS, started=42)
        build.insert()

        outheaders = {}
        outbody = StringIO()
        req = Mock(method='DELETE', base_path='',
                   path_info='/builds/%d' % build.id,
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(204, outheaders['Status'])
        self.assertEqual('', outbody.getvalue())

        # Make sure the started timestamp has been set
        build = Build.fetch(self.env, build.id)
        self.assertEqual(Build.PENDING, build.status)
        assert not build.started

    def test_initiate_build(self):
        config = BuildConfig(self.env, 'test', path='somepath', active=True,
                             recipe='<build></build>')
        config.insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('family', 'posix'))
        platform.insert()
        build = Build(self.env, 'test', '123', platform.id, slave='hal',
                      rev_time=42)
        build.insert()

        outheaders = {}
        outbody = StringIO()
        
        req = Mock(method='GET', base_path='',
                   path_info='/builds/%d' % build.id,
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(200, outheaders['Status'])
        self.assertEqual('90', outheaders['Content-Length'])
        self.assertEqual('application/x-bitten+xml',
                         outheaders['Content-Type'])
        self.assertEqual('attachment; filename=recipe_test_r123.xml',
                         outheaders['Content-Disposition'])
        self.assertEqual('<build build="1" config="test" name="hal"'
                         ' path="somepath" platform="Unix"'
                         ' revision="123"/>',
                         outbody.getvalue())

        # Make sure the started timestamp has been set
        build = Build.fetch(self.env, build.id)
        assert build.started

    def test_initiate_build_no_such_build(self):
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='GET', base_path='',
                   path_info='/builds/123', href=Href('/trac'),
                   remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEquals(404, outheaders['Status'])
        self.assertEquals('No such build (123)', outbody.getvalue())

    def test_process_unknown_collection(self):
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe='<build></build>').insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42)
        build.insert()

        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/files/' % build.id,
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(404, outheaders['Status'])
        self.assertEqual("No such collection 'files'", outbody.getvalue())

    def test_process_build_step_success(self):
        recipe = """<build>
  <step id="foo">
  </step>
</build>"""
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe=recipe).insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42, status=Build.IN_PROGRESS)
        build.slave_info[Build.TOKEN] = '123';
        build.insert()

        inbody = StringIO("""<result step="foo" status="success"
                                     time="2007-04-01T15:30:00.0000"
                                     duration="3.45">
</result>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), abs_href=Href('http://example.org/trac'),
                   remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth=123'))
        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(201, outheaders['Status'])
        self.assertEqual('20', outheaders['Content-Length'])
        self.assertEqual('text/plain', outheaders['Content-Type'])
        self.assertEqual('Build step processed', outbody.getvalue())

        build = Build.fetch(self.env, build.id)
        self.assertEqual(Build.SUCCESS, build.status)
        assert build.stopped
        assert build.stopped > build.started

        steps = list(BuildStep.select(self.env, build.id))
        self.assertEqual(1, len(steps))
        self.assertEqual('foo', steps[0].name)
        self.assertEqual(BuildStep.SUCCESS, steps[0].status)

    def test_process_build_step_success_with_log(self):
        recipe = """<build>
  <step id="foo">
  </step>
</build>"""
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe=recipe).insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42, status=Build.IN_PROGRESS)
        build.slave_info[Build.TOKEN] = '123';
        build.insert()

        inbody = StringIO("""<result step="foo" status="success"
                                     time="2007-04-01T15:30:00.0000"
                                     duration="3.45">
    <log generator="http://bitten.cmlenz.net/tools/python#unittest">
        <message level="info">Doing stuff</message>
        <message level="error">Ouch that hurt</message>
    </log>
</result>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), abs_href=Href('http://example.org/trac'),
                   remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth=123'))
        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(201, outheaders['Status'])
        self.assertEqual('20', outheaders['Content-Length'])
        self.assertEqual('text/plain', outheaders['Content-Type'])
        self.assertEqual('Build step processed', outbody.getvalue())

        build = Build.fetch(self.env, build.id)
        self.assertEqual(Build.SUCCESS, build.status)
        assert build.stopped
        assert build.stopped > build.started

        steps = list(BuildStep.select(self.env, build.id))
        self.assertEqual(1, len(steps))
        self.assertEqual('foo', steps[0].name)
        self.assertEqual(BuildStep.SUCCESS, steps[0].status)

        logs = list(BuildLog.select(self.env, build=build.id, step='foo'))
        self.assertEqual(1, len(logs))
        self.assertEqual('http://bitten.cmlenz.net/tools/python#unittest',
                         logs[0].generator)
        self.assertEqual(2, len(logs[0].messages))
        self.assertEqual((u'info', u'Doing stuff'), logs[0].messages[0])
        self.assertEqual((u'error', u'Ouch that hurt'), logs[0].messages[1])

    def test_process_build_step_success_with_report(self):
        recipe = """<build>
  <step id="foo">
  </step>
</build>"""
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe=recipe).insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42, status=Build.IN_PROGRESS)
        build.slave_info[Build.TOKEN] = '123';
        build.insert()

        inbody = StringIO("""<result step="foo" status="success"
                                     time="2007-04-01T15:30:00.0000"
                                     duration="3.45">
    <report category="test"
            generator="http://bitten.cmlenz.net/tools/python#unittest">
        <test fixture="my.Fixture" file="my/test/file.py">
            <stdout>Doing my thing</stdout>
        </test>
    </report>
</result>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), abs_href=Href('http://example.org/trac'),
                   remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth=123'))
        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(201, outheaders['Status'])
        self.assertEqual('20', outheaders['Content-Length'])
        self.assertEqual('text/plain', outheaders['Content-Type'])
        self.assertEqual('Build step processed', outbody.getvalue())

        build = Build.fetch(self.env, build.id)
        self.assertEqual(Build.SUCCESS, build.status)
        assert build.stopped
        assert build.stopped > build.started

        steps = list(BuildStep.select(self.env, build.id))
        self.assertEqual(1, len(steps))
        self.assertEqual('foo', steps[0].name)
        self.assertEqual(BuildStep.SUCCESS, steps[0].status)

        reports = list(Report.select(self.env, build=build.id, step='foo'))
        self.assertEqual(1, len(reports))
        self.assertEqual('test', reports[0].category)
        self.assertEqual('http://bitten.cmlenz.net/tools/python#unittest',
                         reports[0].generator)
        self.assertEqual(1, len(reports[0].items))
        self.assertEqual({
            'fixture': 'my.Fixture', 
            'file': 'my/test/file.py', 
            'stdout': 'Doing my thing',
            'type': 'test',
        }, reports[0].items[0])

    def test_process_build_step_success_with_attach(self):
        # Parse input and create attachments for config + build
        recipe = """<build>
  <step id="foo">
  <attach file="bar.txt" description="bar bar"/>
  <attach file="baz.txt" description="baz baz" resource="config"/>
  </step>
</build>"""
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe=recipe).insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42, status=Build.IN_PROGRESS)
        build.slave_info[Build.TOKEN] = '123';
        build.insert()

        inbody = StringIO("""<result step="foo" status="success"
                                     time="2007-04-01T15:30:00.0000"
                                     duration="3.45">
    <attach>
        <file filename="bar.txt"
              description="bar bar">aGVsbG8gYmFy\n</file>
    </attach>
    <attach>
        <file filename="baz.txt" description="baz baz"
            resource="config">aGVsbG8gYmF6\n</file>
    </attach>
</result>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), abs_href=Href('http://example.org/trac'),
                   remote_addr='127.0.0.1', args={},
                   authname='hal',
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth=123'))
        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(201, outheaders['Status'])
        self.assertEqual('20', outheaders['Content-Length'])
        self.assertEqual('text/plain', outheaders['Content-Type'])
        self.assertEqual('Build step processed', outbody.getvalue())

        build = Build.fetch(self.env, build.id)
        self.assertEqual(Build.SUCCESS, build.status)
        assert build.stopped
        assert build.stopped > build.started

        steps = list(BuildStep.select(self.env, build.id))
        self.assertEqual(1, len(steps))
        self.assertEqual('foo', steps[0].name)
        self.assertEqual(BuildStep.SUCCESS, steps[0].status)

        from trac.attachment import Attachment
        config_attachments = list(Attachment.select(self.env, 'build', 'test'))
        build_attachments = list(Attachment.select(self.env, 'build', 'test/1'))
        
        self.assertEquals(1, len(build_attachments))
        self.assertEquals('hal', build_attachments[0].author)
        self.assertEquals('bar bar', build_attachments[0].description)
        self.assertEquals('bar.txt', build_attachments[0].filename)
        self.assertEquals('hello bar',
                        build_attachments[0].open().read())

        self.assertEquals(1, len(config_attachments))
        self.assertEquals('hal', config_attachments[0].author)
        self.assertEquals('baz baz', config_attachments[0].description)
        self.assertEquals('baz.txt', config_attachments[0].filename)
        self.assertEquals('hello baz',
                        config_attachments[0].open().read())

    def test_process_build_step_wrong_slave(self):
        recipe = """<build>
  <step id="foo">
  </step>
</build>"""
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe=recipe).insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42, status=Build.IN_PROGRESS)
        build.slave_info[Build.TOKEN] = '123';
        build.insert()

        inbody = StringIO("""<result step="foo" status="success"
                                     time="2007-04-01T15:30:00.0000"
                                     duration="3.45">
    <log generator="http://bitten.cmlenz.net/tools/python#unittest">
        <message level="info">Doing stuff</message>
        <message level="error">Ouch that hurt</message>
    </log>
</result>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), abs_href=Href('http://example.org/trac'),
                   remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))
        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(409, outheaders['Status'])
        self.assertEqual('Token mismatch (wrong slave): slave=, build=123',
                        outbody.getvalue())

        build = Build.fetch(self.env, build.id)
        self.assertEqual(Build.IN_PROGRESS, build.status)
        assert not build.stopped

        steps = list(BuildStep.select(self.env, build.id))
        self.assertEqual(0, len(steps))

    def test_process_build_step_invalidated_build(self):
        recipe = """<build>
  <step id="foo">
  </step>
  <step id="foo2">
  </step>
</build>"""
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe=recipe).insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42, status=Build.IN_PROGRESS)
        build.slave_info[Build.TOKEN] = '123';
        build.insert()

        inbody = StringIO("""<result step="foo" status="success"
                                     time="2007-04-01T15:30:00.0000"
                                     duration="3.45">
    <log generator="http://bitten.cmlenz.net/tools/python#unittest">
        <message level="info">Doing stuff</message>
        <message level="error">Ouch that hurt</message>
    </log>
</result>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), abs_href=Href('http://example.org/trac'),
                   remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth=123'))
        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        build = Build.fetch(self.env, build.id)
        self.assertEqual(Build.IN_PROGRESS, build.status)
        assert not build.stopped

        steps = list(BuildStep.select(self.env, build.id))
        self.assertEqual(1, len(steps))

        # invalidate the build. 

        build = Build.fetch(self.env, build.id)
        build.slave = None
        build.status = Build.PENDING
        build.update()

        # have this slave submit more data.
        inbody = StringIO("""<result step="foo2" status="success"
                                     time="2007-04-01T15:45:00.0000"
                                     duration="4">
    <log generator="http://bitten.cmlenz.net/tools/python#unittest">
        <message level="info">This is a step after invalidation</message>
    </log>
</result>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), abs_href=Href('http://example.org/trac'),
                   remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth=123'))
        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEquals(409, outheaders['Status'])
        self.assertEquals('Build 1 has been invalidated for host 127.0.0.1.',
                        outbody.getvalue())            

        build = Build.fetch(self.env, build.id)
        self.assertEqual(Build.PENDING, build.status)

    def test_process_build_step_failure(self):
        recipe = """<build>
  <step id="foo">
  </step>
</build>"""
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe=recipe).insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42, status=Build.IN_PROGRESS)
        build.slave_info[Build.TOKEN] = '123';
        build.insert()

        inbody = StringIO("""<result step="foo" status="failure"
                                     time="2007-04-01T15:30:00.0000"
                                     duration="3.45">
</result>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), abs_href=Href('http://example.org/trac'),
                   remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth=123'))
        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(201, outheaders['Status'])
        self.assertEqual('20', outheaders['Content-Length'])
        self.assertEqual('text/plain', outheaders['Content-Type'])
        self.assertEqual('Build step processed', outbody.getvalue())

        build = Build.fetch(self.env, build.id)
        self.assertEqual(Build.FAILURE, build.status)
        assert build.stopped
        assert build.stopped > build.started

        steps = list(BuildStep.select(self.env, build.id))
        self.assertEqual(1, len(steps))
        self.assertEqual('foo', steps[0].name)
        self.assertEqual(BuildStep.FAILURE, steps[0].status)

    def test_process_build_step_failure_ignored(self):
        recipe = """<build>
  <step id="foo" onerror="ignore">
  </step>
</build>"""
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe=recipe).insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42, status=Build.IN_PROGRESS)
        build.slave_info[Build.TOKEN] = '123';

        build.insert()

        inbody = StringIO("""<result step="foo" status="failure"
                                     time="2007-04-01T15:30:00.0000"
                                     duration="3.45">
</result>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), abs_href=Href('http://example.org/trac'),
                   remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth=123'))
        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(201, outheaders['Status'])
        self.assertEqual('20', outheaders['Content-Length'])
        self.assertEqual('text/plain', outheaders['Content-Type'])
        self.assertEqual('Build step processed', outbody.getvalue())

        build = Build.fetch(self.env, build.id)
        self.assertEqual(Build.SUCCESS, build.status)
        assert build.stopped
        assert build.stopped > build.started

        steps = list(BuildStep.select(self.env, build.id))
        self.assertEqual(1, len(steps))
        self.assertEqual('foo', steps[0].name)
        self.assertEqual(BuildStep.FAILURE, steps[0].status)

    def test_process_build_step_invalid_xml(self):
        recipe = """<build>
  <step id="foo">
  </step>
</build>"""
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe=recipe).insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42)
        build.insert()

        inbody = StringIO("""<result></rsleut>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEquals(400, outheaders['Status'])
        self.assertEquals('XML parser error', outbody.getvalue())

    def test_process_build_step_invalid_datetime(self):
        recipe = """<build>
  <step id="foo">
  </step>
</build>"""
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe=recipe).insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42, status=Build.IN_PROGRESS)
        build.slave_info[Build.TOKEN] = '123';
        build.insert()

        inbody = StringIO("""<result step="foo" status="success"
                                     time="sometime tomorrow maybe"
                                     duration="3.45">
</result>""")
        outheaders = {}
        outbody = StringIO()
        req = Mock(method='POST', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   read=inbody.read,
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth=123'))

        module = BuildMaster(self.env)
        assert module.match_request(req)

        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEquals(400, outheaders['Status'])
        self.assertEquals("Invalid ISO date/time 'sometime tomorrow maybe'",
                             outbody.getvalue())

    def test_process_build_step_no_post(self):
        BuildConfig(self.env, 'test', path='somepath', active=True,
                    recipe='<build></build>').insert()
        build = Build(self.env, 'test', '123', 1, slave='hal', rev_time=42,
                      started=42)
        build.insert()

        outheaders = {}
        outbody = StringIO()
        req = Mock(method='GET', base_path='',
                   path_info='/builds/%d/steps/' % build.id,
                   href=Href('/trac'), remote_addr='127.0.0.1', args={},
                   perm=PermissionCache(self.env, 'hal'),
                   send_response=lambda x: outheaders.setdefault('Status', x),
                   send_header=lambda x, y: outheaders.setdefault(x, y),
                   write=outbody.write,
                   incookie=Cookie('trac_auth='))

        module = BuildMaster(self.env)
        assert module.match_request(req)
        
        self.assertRaises(RequestDone, module.process_request, req)

        self.assertEqual(405, outheaders['Status'])
        self.assertEqual('Method GET not allowed', outbody.getvalue())


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(BuildMasterTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
