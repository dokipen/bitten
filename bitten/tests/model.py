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

import unittest

from trac.test import EnvironmentStub
from bitten.model import Build, BuildConfig, TargetPlatform


class BuildConfigTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        for table in BuildConfig._schema:
            cursor.execute(db.to_sql(table))
        db.commit()

    def test_new_config(self):
        config = BuildConfig(self.env)
        assert not config.exists

    def test_insert_config(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.label = 'Test'
        config.path = 'trunk'
        config.insert()

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT name,path,label,active,description "
                       "FROM bitten_config")
        self.assertEqual(('test', 'trunk', 'Test', 0, ''), cursor.fetchone())

    def test_insert_config_no_name(self):
        config = BuildConfig(self.env)
        self.assertRaises(AssertionError, config.insert)


class TargetPlatformTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        for table in TargetPlatform._schema:
            cursor.execute(db.to_sql(table))
        db.commit()

    def test_new(self):
        platform = TargetPlatform(self.env)
        self.assertEqual(False, platform.exists)
        self.assertEqual([], platform.rules)

    def test_insert(self):
        platform = TargetPlatform(self.env)
        platform.config = 'test'
        platform.name = 'Windows XP'
        platform.rules.append((Build.OS_NAME, 'Windows'))
        platform.rules.append((Build.OS_VERSION, 'XP'))
        platform.insert()

        assert platform.exists
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT config,name FROM bitten_platform "
                       "WHERE id=%s", (platform.id,))
        self.assertEqual(('test', 'Windows XP'), cursor.fetchone())

        cursor.execute("SELECT propname,pattern,orderno FROM bitten_rule "
                       "WHERE id=%s", (platform.id,))
        self.assertEqual((Build.OS_NAME, 'Windows', 0), cursor.fetchone())
        self.assertEqual((Build.OS_VERSION, 'XP', 1), cursor.fetchone())

    def test_fetch(self):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("INSERT INTO bitten_platform (config,name) "
                       "VALUES (%s,%s)", ('test', 'Windows'))
        id = db.get_last_id('bitten_platform')
        platform = TargetPlatform(self.env, id)
        assert platform.exists
        self.assertEqual('test', platform.config)
        self.assertEqual('Windows', platform.name)

    def test_select(self):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.executemany("INSERT INTO bitten_platform (config,name) "
                           "VALUES (%s,%s)", [('test', 'Windows'),
                           ('test', 'Mac OS X')])
        platforms = list(TargetPlatform.select(self.env, config='test'))
        self.assertEqual(2, len(platforms))


class BuildTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        for table in Build._schema:
            cursor.execute(db.to_sql(table))
        db.commit()

    def test_new(self):
        build = Build(self.env)
        self.assertEqual(None, build.id)
        self.assertEqual(Build.PENDING, build.status)
        self.assertEqual(0, build.stopped)
        self.assertEqual(0, build.started)

    def test_insert(self):
        build = Build(self.env)
        build.config = 'test'
        build.rev = '42'
        build.rev_time = 12039
        build.slave_info[Build.IP_ADDRESS] = '127.0.0.1'
        build.slave_info[Build.MAINTAINER] = 'joe@example.org'
        build.insert()

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT config,rev,slave,started,stopped,status "
                       "FROM bitten_build WHERE id=%s" % build.id)
        self.assertEqual(('test', '42', '', 0, 0, 'P'), cursor.fetchone())

        cursor.execute("SELECT propname,propvalue FROM bitten_slave")
        expected = {Build.IP_ADDRESS: '127.0.0.1',
                    Build.MAINTAINER: 'joe@example.org'}
        for propname, propvalue in cursor:
            self.assertEqual(expected[propname], propvalue)

    def test_insert_no_config_or_rev_or_rev_time(self):
        build = Build(self.env)
        self.assertRaises(AssertionError, build.insert)

        build = Build(self.env)
        build.config = 'test'
        build.rev_time = 12039
        self.assertRaises(AssertionError, build.insert)

        build = Build(self.env)
        build.rev = '42'
        build.rev_time = 12039
        self.assertRaises(AssertionError, build.insert)

        build = Build(self.env)
        build.config = 'test'
        build.rev = '42'
        self.assertRaises(AssertionError, build.insert)

    def test_insert_no_slave(self):
        build = Build(self.env)
        build.config = 'test'
        build.rev = '42'
        build.rev_time = 12039
        build.status = Build.SUCCESS
        self.assertRaises(AssertionError, build.insert)
        build.status = Build.FAILURE
        self.assertRaises(AssertionError, build.insert)
        build.status = Build.IN_PROGRESS
        self.assertRaises(AssertionError, build.insert)
        build.status = Build.PENDING
        build.insert()

    def test_insert_invalid_status(self):
        build = Build(self.env)
        build.config = 'test'
        build.rev = '42'
        build.rev_time = 12039
        build.status = 'DUNNO'
        self.assertRaises(AssertionError, build.insert)

    def test_fetch(self):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("INSERT INTO bitten_build (config,rev,rev_time,slave,"
                       "started,stopped,status) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       ('test', '42', 12039, 'tehbox', 15006, 16007,
                        Build.SUCCESS))
        build_id = db.get_last_id('bitten_build')
        cursor.executemany("INSERT INTO bitten_slave VALUES (%s,%s,%s)",
                           [(build_id, Build.IP_ADDRESS, '127.0.0.1'),
                            (build_id, Build.MAINTAINER, 'joe@example.org')])

        build = Build(self.env, build_id)
        self.assertEquals(build_id, build.id)
        self.assertEquals('127.0.0.1', build.slave_info[Build.IP_ADDRESS])
        self.assertEquals('joe@example.org', build.slave_info[Build.MAINTAINER])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(BuildConfigTestCase, 'test'))
    suite.addTest(unittest.makeSuite(TargetPlatformTestCase, 'test'))
    suite.addTest(unittest.makeSuite(BuildTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
