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
from bitten.model import Build, BuildConfig


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
        self.assertEqual(Build.PENDING, build.status)
        self.assertEqual(0, build.time)
        self.assertEqual(0, build.duration)

    def test_insert_build(self):
        build = Build(self.env)
        build.config = 'test'
        build.rev = '42'
        build.insert()

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT config,rev,slave,time,duration,status "
                       "FROM bitten_build")
        self.assertEqual(('test', '42', '', 0, 0, 'P'), cursor.fetchone())

    def test_insert_build_no_config_or_rev(self):
        build = Build(self.env)
        self.assertRaises(AssertionError, build.insert)

        build = Build(self.env)
        build.config = 'test'
        self.assertRaises(AssertionError, build.insert)

        build = Build(self.env)
        build.rev = '42'
        self.assertRaises(AssertionError, build.insert)

    def test_insert_build_no_slave(self):
        build = Build(self.env)
        build.config = 'test'
        build.rev = '42'
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
        build.status = 'DUNNO'
        self.assertRaises(AssertionError, build.insert)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(BuildConfigTestCase, 'test'))
    suite.addTest(unittest.makeSuite(BuildTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
