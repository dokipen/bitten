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
from bitten.model import Build, BuildConfig, SlaveInfo


class BuildConfigTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(db.to_sql(BuildConfig._table))
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


class BuildTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(db.to_sql(Build._table))
        db.commit()

    def test_new_build(self):
        build = Build(self.env)
        self.assertEqual(None, build.id)
        self.assertEqual(Build.PENDING, build.status)
        self.assertEqual(0, build.stopped)
        self.assertEqual(0, build.started)

    def test_insert_build(self):
        build = Build(self.env)
        build.config = 'test'
        build.rev = '42'
        build.rev_time = 12039
        build.insert()

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT config,rev,slave,started,stopped,status "
                       "FROM bitten_build WHERE id=%s" % build.id)
        self.assertEqual(('test', '42', '', 0, 0, 'P'), cursor.fetchone())

    def test_insert_build_no_config_or_rev_or_rev_time(self):
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

    def test_insert_build_no_slave(self):
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


class SlaveInfoTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute(db.to_sql(SlaveInfo._table))
        db.commit()

    def test_insert_slave_info(self):
        slave_info = SlaveInfo(self.env)
        slave_info.build = 42
        slave_info[SlaveInfo.IP_ADDRESS] = '127.0.0.1'
        slave_info[SlaveInfo.MAINTAINER] = 'joe@example.org'
        slave_info.insert()

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT propname,propvalue FROM bitten_slave")
        expected = {SlaveInfo.IP_ADDRESS: '127.0.0.1',
                    SlaveInfo.MAINTAINER: 'joe@example.org'}
        for propname, propvalue in cursor:
            self.assertEqual(expected[propname], propvalue)

    def test_fetch_slave_info(self):
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.executemany("INSERT INTO bitten_slave VALUES (42,%s,%s)",
                           [(SlaveInfo.IP_ADDRESS, '127.0.0.1'),
                            (SlaveInfo.MAINTAINER, 'joe@example.org')])

        slave_info = SlaveInfo(self.env, 42)
        self.assertEquals(42, slave_info.build)
        self.assertEquals('127.0.0.1', slave_info[SlaveInfo.IP_ADDRESS])
        self.assertEquals('joe@example.org', slave_info[SlaveInfo.MAINTAINER])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(BuildConfigTestCase, 'test'))
    suite.addTest(unittest.makeSuite(BuildTestCase, 'test'))
    suite.addTest(unittest.makeSuite(SlaveInfoTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
