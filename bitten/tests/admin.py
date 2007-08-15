# -*- coding: utf-8 -*-
#
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import shutil
import tempfile
import unittest

from trac.core import TracError
from trac.db import DatabaseManager
from trac.perm import PermissionCache, PermissionSystem
from trac.test import EnvironmentStub, Mock
from trac.versioncontrol import Repository
from trac.web.clearsilver import HDFWrapper
from trac.web.href import Href
from trac.web.main import Request, RequestDone
from bitten.main import BuildSystem
from bitten.model import BuildConfig, TargetPlatform, Build, schema
from bitten.admin import BuildMasterAdminPageProvider, \
                         BuildConfigurationsAdminPageProvider


class BuildMasterAdminPageProviderTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = tempfile.mkdtemp()

        # Create tables
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        connector, _ = DatabaseManager(self.env)._get_connector()
        for table in schema:
            for stmt in connector.to_sql(table):
                cursor.execute(stmt)

        # Set up permissions
        self.env.config.set('trac', 'permission_store',
                            'DefaultPermissionStore')
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')

        # Hook up a dummy repository
        self.repos = Mock(
            get_node=lambda path, rev=None: Mock(get_history=lambda: [],
                                                 isdir=True),
            normalize_path=lambda path: path,
            sync=lambda: None
        )
        self.env.get_repository = lambda authname=None: self.repos

    def tearDown(self):
        shutil.rmtree(self.env.path)

    def test_get_admin_pages(self):
        provider = BuildMasterAdminPageProvider(self.env)

        req = Mock(perm=PermissionCache(self.env, 'joe'))
        self.assertEqual([('bitten', 'Builds', 'master', 'Master Settings')],
                         list(provider.get_admin_pages(req)))

        PermissionSystem(self.env).revoke_permission('joe', 'BUILD_ADMIN')
        req = Mock(perm=PermissionCache(self.env, 'joe'))
        self.assertEqual([], list(provider.get_admin_pages(req)))

    def test_process_get_request(self):
        provider = BuildMasterAdminPageProvider(self.env)

        data = {}
        req = Mock(method='GET', hdf=data,
                   perm=PermissionCache(self.env, 'joe'))
        template_name, content_type = provider.process_admin_request(
            req, 'bitten', 'master', ''
        )
        self.assertEqual('bitten_admin_master.cs', template_name)
        self.assertEqual(None, content_type)
        assert 'admin.master' in data
        self.assertEqual({
            'slave_timeout': 3600,
            'adjust_timestamps': False,
            'build_all': False,
        }, data['admin.master'])


class BuildConfigurationsAdminPageProviderTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = tempfile.mkdtemp()

        # Create tables
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        connector, _ = DatabaseManager(self.env)._get_connector()
        for table in schema:
            for stmt in connector.to_sql(table):
                cursor.execute(stmt)

        # Set up permissions
        self.env.config.set('trac', 'permission_store',
                            'DefaultPermissionStore')
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_MODIFY')

        # Hook up a dummy repository
        self.repos = Mock(
            get_node=lambda path, rev=None: Mock(get_history=lambda: [],
                                                 isdir=True),
            normalize_path=lambda path: path,
            sync=lambda: None
        )
        self.env.get_repository = lambda authname=None: self.repos

    def tearDown(self):
        shutil.rmtree(self.env.path)

    def test_get_admin_pages(self):
        provider = BuildConfigurationsAdminPageProvider(self.env)

        req = Mock(perm=PermissionCache(self.env, 'joe'))
        self.assertEqual([('bitten', 'Builds', 'configs', 'Configurations')],
                         list(provider.get_admin_pages(req)))

        PermissionSystem(self.env).revoke_permission('joe', 'BUILD_MODIFY')
        req = Mock(perm=PermissionCache(self.env, 'joe'))
        self.assertEqual([], list(provider.get_admin_pages(req)))

    def test_process_get_request_overview_empty(self):
        provider = BuildConfigurationsAdminPageProvider(self.env)

        data = {}
        req = Mock(method='GET', hdf=data,
                   perm=PermissionCache(self.env, 'joe'))
        template_name, content_type = provider.process_admin_request(
            req, 'bitten', 'configs', ''
        )
        self.assertEqual('bitten_admin_configs.cs', template_name)
        self.assertEqual(None, content_type)
        self.assertEqual([], data['admin']['configs'])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(
        BuildMasterAdminPageProviderTestCase, 'test'
    ))
    suite.addTest(unittest.makeSuite(
        BuildConfigurationsAdminPageProviderTestCase, 'test'
    ))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
