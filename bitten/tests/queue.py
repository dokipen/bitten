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

from trac.test import EnvironmentStub
from bitten.model import BuildConfig, TargetPlatform, Build, BuildStep, schema
from bitten.queue import BuildQueue


class BuildQueueTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = tempfile.mkdtemp()
        os.mkdir(os.path.join(self.env.path, 'snapshots'))
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        for table in schema:
            for stmt in db.to_sql(table):
                cursor.execute(stmt)
        db.commit()

    def tearDown(self):
        shutil.rmtree(self.env.path)

    def test_next_pending_build(self):
        """
        Make sure that a pending build of an activated configuration is
        scheduled for a slave that matches the target platform.
        """
        BuildConfig(self.env, 'test', active=True).insert()
        build = Build(self.env, config='test', platform=1, rev=123, rev_time=42,
                      status=Build.PENDING)
        build.insert()
        build_id = build.id

        queue = BuildQueue(self.env)
        queue.slaves[1] = ['foobar']
        build, slave = queue.get_next_pending_build(['foobar', 'dummy'])
        self.assertEqual((build_id, 'foobar'), (build.id, slave))

    def test_next_pending_build_no_matching_slave(self):
        """
        Make sure that builds for which there is no slave matching the target
        platform are not scheduled.
        """
        BuildConfig(self.env, 'test', active=True).insert()
        build = Build(self.env, config='test', platform=1, rev=123, rev_time=42,
                      status=Build.PENDING)
        build.insert()
        build_id = build.id

        queue = BuildQueue(self.env)
        queue.slaves[2] = ['foobar']
        build, slave = queue.get_next_pending_build(['foobar', 'dummy'])
        self.assertEqual((None, None), (build, slave))

    def test_next_pending_build_inactive_config(self):
        """
        Make sure that builds for a deactived build config are not scheduled.
        """
        BuildConfig(self.env, 'test').insert()
        build = Build(self.env, config='test', platform=1, rev=123, rev_time=42,
                      status=Build.PENDING)
        build.insert()

        queue = BuildQueue(self.env)
        queue.slaves[1] = ['foobar']
        build, slave = queue.get_next_pending_build(['foobar', 'dummy'])
        self.assertEqual((None, None), (build, slave))

    def test_next_pending_build_slave_round_robin(self):
        """
        Verify that if a slave is selected for a pending build, it is moved to
        the end of the slave list for that target platform.
        """
        BuildConfig(self.env, 'test', active=True).insert()
        build = Build(self.env, config='test', platform=1, rev=123, rev_time=42,
                      status=Build.PENDING)
        build.insert()

        queue = BuildQueue(self.env)
        queue.slaves[1] = ['foo', 'bar', 'baz']
        build, slave = queue.get_next_pending_build(['foo'])
        self.assertEqual(['bar', 'baz', 'foo'], queue.slaves[1])

    def test_register_slave_match_simple(self):
        BuildConfig(self.env, 'test', active=True).insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('family', 'posix'))
        platform.insert()

        queue = BuildQueue(self.env)
        assert queue.register_slave('foo', {'family': 'posix'})
        self.assertEqual(['foo'], queue.slaves[platform.id])

    def test_register_slave_match_simple_fail(self):
        BuildConfig(self.env, 'test', active=True).insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('family', 'posix'))
        platform.insert()

        queue = BuildQueue(self.env)
        assert not queue.register_slave('foo', {'family': 'nt'})
        self.assertEqual([], queue.slaves[platform.id])

    def test_register_slave_match_regexp(self):
        BuildConfig(self.env, 'test', active=True).insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('version', '8\.\d\.\d'))
        platform.insert()

        queue = BuildQueue(self.env)
        assert queue.register_slave('foo', {'version': '8.2.0'})
        self.assertEqual(['foo'], queue.slaves[platform.id])

    def test_register_slave_match_regexp_fail(self):
        BuildConfig(self.env, 'test', active=True).insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('version', '8\.\d\.\d'))
        platform.insert()

        queue = BuildQueue(self.env)
        assert not queue.register_slave('foo', {'version': '7.8.1'})
        self.assertEqual([], queue.slaves[platform.id])

    def test_register_slave_match_regexp_invalid(self):
        BuildConfig(self.env, 'test', active=True).insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('version', '8(\.\d'))
        platform.insert()

        queue = BuildQueue(self.env)
        assert not queue.register_slave('foo', {'version': '7.8.1'})
        self.assertEqual([], queue.slaves[platform.id])

    def test_unregister_slave_no_builds(self):
        queue = BuildQueue(self.env)
        queue.slaves[1] = ['foo', 'bar']
        queue.slaves[2] = ['baz']
        queue.unregister_slave('bar')
        self.assertEqual(['foo'], queue.slaves[1])
        self.assertEqual(['baz'], queue.slaves[2])

    def test_unregister_slave_in_progress_build(self):
        build = Build(self.env, config='test', platform=1, rev=123, rev_time=42,
                      slave='foo', status=Build.IN_PROGRESS)
        build.insert()

        queue = BuildQueue(self.env)
        queue.slaves[1] = ['foo', 'bar']
        queue.slaves[2] = ['baz']
        queue.unregister_slave('bar')
        self.assertEqual(['foo'], queue.slaves[1])
        self.assertEqual(['baz'], queue.slaves[2])

        build = Build.fetch(self.env, id=build.id)
        self.assertEqual(Build.PENDING, build.status)
        self.assertEqual('', build.slave)
        self.assertEqual({}, build.slave_info)
        self.assertEqual(0, build.started)

    def test_get_existing_snapshot(self):
        BuildConfig(self.env, 'test', active=True).insert()
        build = Build(self.env, config='test', platform=1, rev=123, rev_time=42,
                      status=Build.PENDING)
        build.insert()
        snapshot = os.path.join(self.env.path, 'snapshots', 'test_r123.zip')
        snapshot_file = file(snapshot, 'w')
        snapshot_file.close()

        queue = BuildQueue(self.env)
        self.assertEqual(snapshot, queue.get_snapshot(build, 'zip'))


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(BuildQueueTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
