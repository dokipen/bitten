# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
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
from trac.perm import PermissionCache, PermissionSystem
from trac.test import EnvironmentStub, Mock
from trac.versioncontrol import Repository
from trac.web.clearsilver import HDFWrapper
from trac.web.href import Href
from trac.web.main import Request, RequestDone
from bitten.model import BuildConfig, TargetPlatform, Build, schema
from bitten.trac_ext.compat import schema_to_sql
from bitten.trac_ext.main import BuildSystem
from bitten.trac_ext.web_ui import BuildConfigController


class BuildConfigControllerTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = tempfile.mkdtemp()

        # Create tables
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        for table in schema:
            for stmt in schema_to_sql(self.env, db, table):
                cursor.execute(stmt)

        # Set up permissions
        self.env.config.set('trac', 'permission_store',
                            'DefaultPermissionStore')

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

    def test_overview(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_VIEW')
        req = Mock(method='GET', base_path='', cgi_location='',
                   path_info='/build', href=Href('/trac'), args={}, chrome={},
                   hdf=HDFWrapper(), perm=PermissionCache(self.env, 'joe'))

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('overview', req.hdf['page.mode'])
        self.assertEqual('0', req.hdf.get('build.can_create', '0'))

    def test_overview_admin(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='GET', base_path='', cgi_location='',
                   path_info='/build', href=Href('/trac'), args={}, chrome={},
                   hdf=HDFWrapper(), perm=PermissionCache(self.env, 'joe'))

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('1', req.hdf.get('config.can_create'))

    def test_view_config(self):
        config = BuildConfig(self.env, name='test', path='trunk')
        config.insert()
        platform = TargetPlatform(self.env, config='test', name='any')
        platform.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_VIEW')
        req = Mock(method='GET', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'), args={},
                   chrome={}, hdf=HDFWrapper(), authname='joe',
                   perm=PermissionCache(self.env, 'joe'))

        root = Mock(get_entries=lambda: ['foo'],
                    get_history=lambda: [('trunk', rev, 'edit') for rev in
                                          range(123, 111, -1)])
        self.repos = Mock(get_node=lambda path, rev=None: root,
                          sync=lambda: None, normalize_path=lambda path: path)

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('view_config', req.hdf['page.mode'])
        self.assertEqual('0', req.hdf.get('build.config.can_delete', '0'))
        self.assertEqual('0', req.hdf.get('build.config.can_modify', '0'))
        self.assertEqual(None, req.hdf.get('chrome.links.next.0.href'))

    def test_view_config_paging(self):
        config = BuildConfig(self.env, name='test', path='trunk')
        config.insert()
        platform = TargetPlatform(self.env, config='test', name='any')
        platform.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_VIEW')
        req = Mock(method='GET', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'), args={},
                   chrome={}, hdf=HDFWrapper(), authname='joe',
                   perm=PermissionCache(self.env, 'joe'))

        root = Mock(get_entries=lambda: ['foo'],
                    get_history=lambda: [('trunk', rev, 'edit') for rev in
                                          range(123, 110, -1)])
        self.repos = Mock(get_node=lambda path, rev=None: root,
                          sync=lambda: None, normalize_path=lambda path: path)

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        module.process_request(req)

        if req.chrome: # Trac 0.11
            self.assertEqual('/trac/build/test?page=2',
                             req.chrome['links']['next'][0]['href'])
        else:
            self.assertEqual('/trac/build/test?page=2',
                             req.hdf.get('chrome.links.next.0.href'))

    def test_view_config_admin(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='GET', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'), args={},
                   chrome={}, hdf=HDFWrapper(), authname='joe',
                   perm=PermissionCache(self.env, 'joe'))

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('1', req.hdf.get('config.can_delete'))
        self.assertEqual('1', req.hdf.get('config.can_modify'))

    def test_new_config(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='GET', base_path='', cgi_location='',
                   path_info='/build', args={'action': 'new'}, hdf=HDFWrapper(),
                   href=Href('/trac'), chrome={},
                   perm=PermissionCache(self.env, 'joe'))

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('edit_config', req.hdf['page.mode'])

    def test_new_config_submit(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build', href=Href('/trac'), redirect=redirect,
                   hdf=HDFWrapper(), authname='joe',
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'name': 'test', 'path': 'test/trunk',
                         'label': 'Test', 'description': 'Bla bla'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac/build/test', redirected_to[0])

        config = BuildConfig.fetch(self.env, 'test')
        assert config.exists
        assert not config.active
        self.assertEqual('Test', config.label)
        self.assertEqual('test/trunk', config.path)
        self.assertEqual('Bla bla', config.description)

    def test_new_config_submit_without_name(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build', href=Href('/trac'), hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'name': '', 'path': 'test/trunk',
                         'label': 'Test', 'description': 'Bla bla'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(TracError, module.process_request, req)

    def test_new_config_submit_with_invalid_name(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build', href=Href('/trac'), hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'name': 'Foo bar',
                         'path': 'test/trunk', 'label': 'Test',
                         'description': 'Bla bla'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(TracError, module.process_request, req)

    def test_new_config_submit_invalid_path(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build', href=Href('/trac'), hdf=HDFWrapper(),
                   authname='joe', perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'name': 'test', 'path': 'test/trunk',
                         'label': 'Test', 'description': 'Bla bla'})

        def get_node(path, rev=None):
            raise TracError('No such node')
        self.repos = Mock(get_node=get_node)

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(TracError, module.process_request, req)

    def test_new_config_submit_with_non_wellformed_recipe(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build', href=Href('/trac'), hdf=HDFWrapper(),
                   authname='joe', perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'name': 'test', 'path': 'test/trunk',
                         'label': 'Test', 'description': 'Bla bla',
                         'recipe': '<build><step>'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(TracError, module.process_request, req)

    def test_new_config_submit_with_invalid_recipe(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build', href=Href('/trac'), hdf=HDFWrapper(),
                   authname='joe', perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'name': 'test', 'path': 'test/trunk',
                         'label': 'Test', 'description': 'Bla bla',
                         'recipe': '<build><step/></build>'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(TracError, module.process_request, req)

    def test_new_config_cancel(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build', href=Href('/trac'), redirect=redirect,
                   hdf=HDFWrapper(), perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'cancel': '1', 'name': 'test'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac/build', redirected_to[0])

        self.assertEqual(None, BuildConfig.fetch(self.env, 'test'))

    def test_delete_config(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='GET', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'), chrome={},
                   hdf=HDFWrapper(), perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'delete'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('delete_config', req.hdf['page.mode'])

    def test_delete_config_submit(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'),
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'delete'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac/build', redirected_to[0])

        self.assertEqual(None, BuildConfig.fetch(self.env, 'test'))

    def test_edit_config_cancel(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'),
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'delete', 'cancel': ''})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac/build/test', redirected_to[0])

        self.assertEqual(True, BuildConfig.fetch(self.env, 'test').exists)

    def test_edit_config(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='GET', base_path='', cgi_location='',
                   path_info='/build/test', hdf=HDFWrapper(),
                   href=Href('/build/test'), chrome={},
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'edit'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('edit_config', req.hdf['page.mode'])

    def test_edit_config_submit(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'),
                   redirect=redirect, hdf=HDFWrapper(),
                   authname='joe', perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'edit', 'name': 'foo', 'path': 'test/trunk',
                         'label': 'Test',  'description': 'Bla bla'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac/build/foo', redirected_to[0])

        self.assertEqual(None, BuildConfig.fetch(self.env, 'test'))

        config = BuildConfig.fetch(self.env, 'foo')
        assert config.exists
        self.assertEqual('Test', config.label)
        self.assertEqual('test/trunk', config.path)
        self.assertEqual('Bla bla', config.description)

    def test_edit_config_cancel(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'),
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'edit', 'cancel': ''})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac/build/test', redirected_to[0])

    def test_new_platform(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='GET', base_path='', cgi_location='',
                   path_info='/build/test', hdf=HDFWrapper(), href=Href('trac'),
                   chrome={}, perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'edit', 'new': '1'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('edit_platform', req.hdf['page.mode'])

    def test_new_platform_submit(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'),
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'name': 'Test'})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac/build/test?action=edit', redirected_to[0])

    def test_new_platform_cancel(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()
 
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'),
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'cancel': ''})
 
        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac/build/test?action=edit', redirected_to[0])

    def test_edit_platform(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()
        platform = TargetPlatform(self.env)
        platform.config = 'test'
        platform.name = 'linux'
        platform.rules.append(('os', 'linux?'))
        platform.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(method='GET', base_path='', cgi_location='',
                   path_info='/build/test', hdf=HDFWrapper(),
                   href=Href('/trac'), chrome={},
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'edit', 'platform': platform.id})

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('edit_platform', req.hdf['page.mode'])

    def test_edit_platform_submit(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()
        platform = TargetPlatform(self.env)
        platform.config = 'test'
        platform.name = 'linux'
        platform.rules.append(('os', 'linux?'))
        platform.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'),
                   redirect=redirect, hdf=HDFWrapper(),
                   args={'action': 'edit', 'platform': platform.id,
                         'name': 'Test'},
                   perm=PermissionCache(self.env, 'joe'))

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac/build/test?action=edit', redirected_to[0])

    def test_edit_platform_cancel(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()
        platform = TargetPlatform(self.env)
        platform.config = 'test'
        platform.name = 'linux'
        platform.rules.append(('os', 'linux'))
        platform.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(method='POST', base_path='', cgi_location='',
                   path_info='/build/test', href=Href('/trac'),
                   redirect=redirect, hdf=HDFWrapper(),
                   args={'action': 'edit', 'platform': platform.id,
                         'cancel': ''},
                   perm=PermissionCache(self.env, 'joe'))

        module = BuildConfigController(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac/build/test?action=edit', redirected_to[0])


def suite():
    return unittest.makeSuite(BuildConfigControllerTestCase, 'test')

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
