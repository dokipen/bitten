# -*- coding: utf-8 -*-
#
# Copyright (C) 2009 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import unittest

import warnings
warnings.filterwarnings('ignore', '^Unknown table')
warnings.filterwarnings('ignore', '^the sets module is deprecated')

from trac.test import EnvironmentStub
from trac.db import Table, Column, Index, DatabaseManager
from bitten.upgrades import update_sequence, drop_index
from bitten import upgrades, main, model

import os
import shutil
import tempfile


class BaseUpgradeTestCase(unittest.TestCase):

    schema = None
    other_tables = []

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.config.set('trac', 'database', self.env.dburi)
        self.env.path = tempfile.mkdtemp()
        logs_dir = self.env.config.get("bitten", "logs_dir")
        if os.path.isabs(logs_dir):
            raise ValueError("Should not have absolute logs directory for temporary test")
        logs_dir = os.path.join(self.env.path, logs_dir)
        if not os.path.isdir(logs_dir):
            os.makedirs(logs_dir)

        db = self.env.get_db_cnx()
        cursor = db.cursor()

        for table_name in self.other_tables:
            cursor.execute("DROP TABLE IF EXISTS %s" % (table_name,))

        connector, _ = DatabaseManager(self.env)._get_connector()
        for table in self.schema:
            cursor.execute("DROP TABLE IF EXISTS %s" % (table.name,))
            for stmt in connector.to_sql(table):
                cursor.execute(stmt)

        db.commit()

    def tearDown(self):
        shutil.rmtree(self.env.path)
        del self.env


class UpgradeHelperTestCase(BaseUpgradeTestCase):

    schema = [
        Table('test_update_sequence', key='id')[
            Column('id', auto_increment=True), Column('name'),
        ],
        Table('test_drop_index', key='id')[
            Column('id', type='int'), Column('name', size=20),
            Index(['name'])
        ],
    ]

    def test_update_sequence(self):
        db = self.env.get_db_cnx()
        cursor = db.cursor()

        for rowid, name in [(1, 'a'), (2, 'b'), (3, 'c')]:
            cursor.execute("INSERT INTO test_update_sequence (id, name)"
                " VALUES (%s, %s)", (rowid, name))
        update_sequence(self.env, db, 'test_update_sequence', 'id')

        cursor.execute("INSERT INTO test_update_sequence (name)"
            " VALUES (%s)", ('d',))

        cursor.execute("SELECT id FROM test_update_sequence WHERE name = %s",
            ('d',))
        row = cursor.fetchone()
        self.assertEqual(row[0], 4)

    def test_drop_index(self):
        db = self.env.get_db_cnx()
        cursor = db.cursor()

        cursor.execute("INSERT INTO test_drop_index (id, name)"
            " VALUES (%s, %s)", (1, 'a'))

        def do_drop():
            drop_index(self.env, db, 'test_drop_index', 'test_drop_index_name_idx')

        # dropping the index should succeed the first time and fail the next
        do_drop()
        self.assertRaises(Exception, do_drop)


class UpgradeScriptsTestCase(BaseUpgradeTestCase):

    schema = [
        # Sytem
        Table('system', key='name')[
            Column('name'), Column('value')
        ],
        # Config
        Table('bitten_config', key='name')[
            Column('name'), Column('path'), Column('label'),
            Column('active', type='int'), Column('description')
        ],
        # Platform
        Table('bitten_platform', key='id')[
            Column('id', auto_increment=True), Column('config'), Column('name')
        ],
        Table('bitten_rule', key=('id', 'propname'))[
            Column('id'), Column('propname'), Column('pattern'),
            Column('orderno', type='int')
        ],
        # Build
        Table('bitten_build', key='id')[
            Column('id', auto_increment=True), Column('config'), Column('rev'),
            Column('rev_time', type='int'), Column('platform', type='int'),
            Column('slave'), Column('started', type='int'),
            Column('stopped', type='int'), Column('status', size=1),
            Index(['config', 'rev', 'slave'])
        ],
        Table('bitten_slave', key=('build', 'propname'))[
            Column('build', type='int'), Column('propname'), Column('propvalue')
        ],
        # Build Step
        Table('bitten_step', key=('build', 'name'))[
            Column('build', type='int'), Column('name'), Column('description'),
            Column('status', size=1), Column('log'),
            Column('started', type='int'), Column('stopped', type='int')
        ],
    ]

    other_tables = [
        'bitten_log',
        'bitten_log_message',
        'bitten_report',
        'bitten_report_item',
        'bitten_error',
        'old_step',
        'old_config',
        'old_log_v5',
        'old_log_v8',
        'old_rule',
    ]

    basic_data = [
        ['system',
            ('name', 'value'), [
                ('bitten_version', '1'),
            ]
        ],
        ['bitten_config',
            ('name',), [
                ('test_config',),
            ]
        ],
        ['bitten_platform',
            ('config', 'name'), [
                ('test_config', 'test_plat'),
            ]
        ],
        ['bitten_build',
            ('config', 'rev', 'platform', 'rev_time'), [
                ('test_config', '123', 1, 456),
            ]
        ],
        ['bitten_step',
            ('build', 'name', 'log'), [
                (1, 'step1', None),
                (1, 'step2', "line1\nline2"),
            ]
        ],
    ]

    def _do_upgrade(self):
        """Do an full upgrade."""
        import inspect
        db = self.env.get_db_cnx()

        versions = sorted(upgrades.map.keys())
        for version in versions:
            for function in upgrades.map.get(version):
                self.assertTrue(inspect.getdoc(function))
                function(self.env, db)

        db.commit()

    def _insert_data(self, data):
        """Insert data for upgrading."""
        db = self.env.get_db_cnx()
        cursor = db.cursor()

        for table, cols, vals in data:
            cursor.executemany("INSERT INTO %s (%s) VALUES (%s)"
                % (table, ','.join(cols),
                ','.join(['%s' for c in cols])),
                vals)

        db.commit()

    def _check_basic_upgrade(self):
        """Check the results of an upgrade of basic data."""
        db = self.env.get_db_cnx()

        configs = list(model.BuildConfig.select(self.env,
            include_inactive=True))
        platforms = list(model.TargetPlatform.select(self.env))
        builds = list(model.Build.select(self.env))
        steps = list(model.BuildStep.select(self.env))
        logs = list(model.BuildLog.select(self.env))

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].name, 'test_config')

        self.assertEqual(len(platforms), 1)
        self.assertEqual(platforms[0].config, 'test_config')
        self.assertEqual(platforms[0].name, 'test_plat')

        self.assertEqual(len(builds), 1)
        self.assertEqual(builds[0].config, 'test_config')
        self.assertEqual(builds[0].rev, '123')
        self.assertEqual(builds[0].platform, 1)
        self.assertEqual(builds[0].rev_time, 456)

        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0].build, 1)
        self.assertEqual(steps[0].name, 'step1')
        self.assertEqual(steps[1].build, 1)
        self.assertEqual(steps[1].name, 'step2')

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].build, 1)
        self.assertEqual(logs[0].step, 'step2')
        log_file = logs[0].get_log_file(logs[0].filename)
        self.assertEqual(file(log_file, "rU").read(), "line1\nline2\n")

    def test_null_upgrade(self):
        self._do_upgrade()

    def test_basic_upgrade(self):
        self._insert_data(self.basic_data)
        self._do_upgrade()
        self._check_basic_upgrade()

    def test_upgrade_via_buildsetup(self):
        self._insert_data(self.basic_data)
        db = self.env.get_db_cnx()
        build_setup = main.BuildSetup(self.env)
        self.assertTrue(build_setup.environment_needs_upgrade(db))
        build_setup.upgrade_environment(db)
        self._check_basic_upgrade()

        # check bitten table version
        cursor = db.cursor()
        cursor.execute("SELECT value FROM system WHERE name='bitten_version'")
        rows = cursor.fetchall()
        self.assertEqual(rows, [(str(model.schema_version),)])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(UpgradeHelperTestCase, 'test'))
    suite.addTest(unittest.makeSuite(UpgradeScriptsTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
