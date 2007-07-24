# -*- coding: utf-8 -*-
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

from trac.test import EnvironmentStub, Mock
from bitten.model import BuildConfig, TargetPlatform, Build, BuildStep, schema
from bitten.queue import BuildQueue, collect_changes
from bitten.trac_ext.compat import schema_to_sql


class CollectChangesTestCase(unittest.TestCase):
    """
    Unit tests for the `bitten.queue.collect_changes` function.
    """

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = tempfile.mkdtemp()
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        for table in schema:
            for stmt in schema_to_sql(self.env, db, table):
                cursor.execute(stmt)
        self.config = BuildConfig(self.env, name='test', path='somepath')
        self.config.insert(db=db)
        self.platform = TargetPlatform(self.env, config='test', name='Foo')
        self.platform.insert(db=db)
        db.commit()

    def tearDown(self):
        shutil.rmtree(self.env.path)

    def test_stop_on_copy(self):
        self.env.get_repository = lambda authname=None: Mock(
            get_node=lambda path, rev=None: Mock(
                get_history=lambda: [('otherpath', 123, 'copy')]
            ),
            normalize_path=lambda path: path
        )

        retval = list(collect_changes(self.env.get_repository(), self.config))
        self.assertEqual(0, len(retval))

    def test_stop_on_minrev(self):
        self.env.get_repository = lambda authname=None: Mock(
            get_node=lambda path, rev=None: Mock(
                get_entries=lambda: [Mock(), Mock()],
                get_history=lambda: [('somepath', 123, 'edit'),
                                     ('somepath', 121, 'edit'),
                                     ('somepath', 120, 'edit')]
            ),
            normalize_path=lambda path: path,
            rev_older_than=lambda rev1, rev2: rev1 < rev2
        )

        self.config.min_rev = 123
        self.config.update()

        retval = list(collect_changes(self.env.get_repository(), self.config))
        self.assertEqual(1, len(retval))
        self.assertEqual(123, retval[0][1])

    def test_skip_until_maxrev(self):
        self.env.get_repository = lambda authname=None: Mock(
            get_node=lambda path, rev=None: Mock(
                get_entries=lambda: [Mock(), Mock()],
                get_history=lambda: [('somepath', 123, 'edit'),
                                     ('somepath', 121, 'edit'),
                                     ('somepath', 120, 'edit')]
            ),
            normalize_path=lambda path: path,
            rev_older_than=lambda rev1, rev2: rev1 < rev2
        )

        self.config.max_rev=121
        self.config.update()

        retval = list(collect_changes(self.env.get_repository(), self.config))
        self.assertEqual(2, len(retval))
        self.assertEqual(121, retval[0][1])
        self.assertEqual(120, retval[1][1])

    def test_skip_empty_dir(self):
        def _mock_get_node(path, rev=None):
            if rev and rev == 121:
                return Mock(
                    get_entries=lambda: []
                )
            else:
                return Mock(
                    get_entries=lambda: [Mock(), Mock()],
                    get_history=lambda: [('somepath', 123, 'edit'),
                                         ('somepath', 121, 'edit'),
                                         ('somepath', 120, 'edit')]
                )

        self.env.get_repository = lambda authname=None: Mock(
            get_node=_mock_get_node,
            normalize_path=lambda path: path,
            rev_older_than=lambda rev1, rev2: rev1 < rev2
        )

        retval = list(collect_changes(self.env.get_repository(), self.config))
        self.assertEqual(2, len(retval))
        self.assertEqual(123, retval[0][1])
        self.assertEqual(120, retval[1][1])


class BuildQueueTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = tempfile.mkdtemp()
        os.mkdir(os.path.join(self.env.path, 'snapshots'))
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        for table in schema:
            for stmt in schema_to_sql(self.env, db, table):
                cursor.execute(stmt)
        db.commit()

        # Hook up a dummy repository
        self.repos = Mock()
        self.env.get_repository = lambda authname=None: self.repos

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
        self.assertRaises(KeyError, queue.slaves.__getitem__, platform.id)

    def test_register_slave_match_regexp(self):
        BuildConfig(self.env, 'test', active=True).insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('version', '8\.\d\.\d'))
        platform.insert()

        queue = BuildQueue(self.env)
        assert queue.register_slave('foo', {'version': '8.2.0'})
        self.assertEqual(['foo'], queue.slaves[platform.id])

    def test_register_slave_match_regexp_multi(self):
        BuildConfig(self.env, 'test', active=True).insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('os', '^Linux'))
        platform.rules.append(('processor', '^[xi]\d?86$'))
        platform.insert()

        queue = BuildQueue(self.env)
        assert queue.register_slave('foo', {'os': 'Linux', 'processor': 'i686'})
        self.assertEqual(['foo'], queue.slaves[platform.id])

    def test_register_slave_match_regexp_fail(self):
        BuildConfig(self.env, 'test', active=True).insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('version', '8\.\d\.\d'))
        platform.insert()

        queue = BuildQueue(self.env)
        assert not queue.register_slave('foo', {'version': '7.8.1'})
        self.assertRaises(KeyError, queue.slaves.__getitem__, platform.id)

    def test_register_slave_match_regexp_invalid(self):
        BuildConfig(self.env, 'test', active=True).insert()
        platform = TargetPlatform(self.env, config='test', name="Unix")
        platform.rules.append(('version', '8(\.\d'))
        platform.insert()

        queue = BuildQueue(self.env)
        assert not queue.register_slave('foo', {'version': '7.8.1'})
        self.assertRaises(KeyError, queue.slaves.__getitem__, platform.id)

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


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(CollectChangesTestCase, 'test'))
    suite.addTest(unittest.makeSuite(BuildQueueTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
