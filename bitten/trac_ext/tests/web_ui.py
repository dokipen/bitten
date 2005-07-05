import unittest

from trac.perm import PermissionCache, PermissionSystem
from trac.test import EnvironmentStub, Mock
from trac.versioncontrol import Repository
from trac.web.clearsilver import HDFWrapper
from trac.web.main import Request, RequestDone
from bitten.model import BuildConfig, TargetPlatform, Build, schema
from bitten.trac_ext.main import BuildSystem
from bitten.trac_ext.web_ui import BuildModule


class BuildModuleTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()

        # Create tables
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        for table in schema:
            cursor.execute(db.to_sql(table))

        # Set up permissions
        self.env.config.set('trac', 'permission_store',
                            'DefaultPermissionStore')

        # Hook up a dummy repository
        repos = Mock(get_node=lambda path: Mock(get_history=lambda: []))
        self.env.get_repository = lambda x: repos

    def test_overview(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_VIEW')
        req = Mock(Request, path_info='/build', args={}, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('overview', req.hdf['build.mode'])
        self.assertEqual('0', req.hdf.get('build.can_create', '0'))

    def test_overview_admin(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(Request, path_info='/build', args={}, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('1', req.hdf.get('build.can_create'))

    def test_view_config(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_VIEW')
        req = Mock(Request, path_info='/build/test', args={}, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('view_config', req.hdf['build.mode'])
        self.assertEqual('0', req.hdf.get('build.config.can_modify', '0'))

    def test_view_config_admin(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(Request, path_info='/build/test', args={}, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('1', req.hdf.get('build.config.can_modify'))

    def test_new_config(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(Request, path_info='/build', args={'action': 'new'},
                   hdf=HDFWrapper(), perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('edit_config', req.hdf['build.mode'])

    def test_new_config_submit(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(Request, method='POST', path_info='/build',
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'name': 'test', 'active': 'on',
                         'label': 'Test', 'path': 'test/trunk',
                         'description': 'Bla bla'})
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac.cgi/build/test', redirected_to[0])

        build = BuildConfig(self.env, 'test')
        assert build.exists
        assert build.active
        self.assertEqual('Test', build.label)
        self.assertEqual('test/trunk', build.path)
        self.assertEqual('Bla bla', build.description)

    def test_new_config_cancel(self):
        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(Request, method='POST', path_info='/build',
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'new', 'cancel': '1', 'name': 'test'})
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac.cgi/build', redirected_to[0])

        self.assertRaises(Exception, BuildConfig, self.env, 'test')

    def test_edit_config(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(Request, path_info='/build/test', args={'action': 'edit'},
                   hdf=HDFWrapper(), perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('edit_config', req.hdf['build.mode'])

    def test_edit_config_submit(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(Request, method='POST', path_info='/build/test',
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'edit', 'name': 'foo', 'active': 'on',
                         'label': 'Test', 'path': 'test/trunk',
                         'description': 'Bla bla'})
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac.cgi/build/foo', redirected_to[0])

        self.assertRaises(Exception, BuildConfig, self.env, 'test')

        build = BuildConfig(self.env, 'foo')
        assert build.exists
        assert build.active
        self.assertEqual('Test', build.label)
        self.assertEqual('test/trunk', build.path)
        self.assertEqual('Bla bla', build.description)

    def test_edit_config_cancel(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(Request, method='POST', path_info='/build/test',
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'),
                   args={'action': 'edit', 'cancel': '1'})
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac.cgi/build/test', redirected_to[0])

    def test_new_platform(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        req = Mock(Request, path_info='/build/test',
                   args={'action': 'edit', 'new': '1'},
                   hdf=HDFWrapper(), perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('edit_platform', req.hdf['build.mode'])

    def test_new_platform_submit(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(Request, method='POST', path_info='/build/test',
                   redirect=redirect, args={'action': 'new', 'name': 'Test'},
                   hdf=HDFWrapper(), perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac.cgi/build/test?action=edit', redirected_to[0])

    def test_new_platform_cancel(self):
        config = BuildConfig(self.env)
        config.name = 'test'
        config.insert()

        PermissionSystem(self.env).grant_permission('joe', 'BUILD_ADMIN')
        redirected_to = []
        def redirect(url):
            redirected_to.append(url)
            raise RequestDone
        req = Mock(Request, method='POST', path_info='/build/test',
                   redirect=redirect, args={'action': 'new', 'cancel': '1'},
                   hdf=HDFWrapper(), perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac.cgi/build/test?action=edit', redirected_to[0])

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
        req = Mock(Request, path_info='/build/test',
                   args={'action': 'edit', 'platform': platform.id},
                   hdf=HDFWrapper(), perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        module.process_request(req)

        self.assertEqual('edit_platform', req.hdf['build.mode'])

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
        req = Mock(Request, method='POST', path_info='/build/test',
                   args={'action': 'edit', 'platform': platform.id,
                         'name': 'Test'},
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac.cgi/build/test?action=edit', redirected_to[0])

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
        req = Mock(Request, method='POST', path_info='/build/test',
                   args={'action': 'edit', 'platform': platform.id,
                         'cancel': '1'},
                   redirect=redirect, hdf=HDFWrapper(),
                   perm=PermissionCache(self.env, 'joe'))
        req.hdf['htdocs_location'] = '/htdocs'

        module = BuildModule(self.env)
        assert module.match_request(req)
        self.assertRaises(RequestDone, module.process_request, req)
        self.assertEqual('/trac.cgi/build/test?action=edit', redirected_to[0])


def suite():
    return unittest.makeSuite(BuildModuleTestCase, 'test')

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
