# -*- coding: utf-8 -*-
#
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

"""Implementation of the web administration interface."""

import re

from trac.core import *
from webadmin.web_ui import IAdminPageProvider

from bitten.model import BuildConfig, TargetPlatform
from bitten.recipe import Recipe
from bitten.util import xmlio


class BuildMasterAdminPageProvider(Component):
    """Web administration panel for configuring the build master."""

    implements(IAdminPageProvider)

    # IAdminPageProvider methods

    def get_admin_pages(self, req):
        if req.perm.has_permission('BUILD_ADMIN'):
            yield ('bitten', 'Bitten', 'master', 'Build Master')

    def process_admin_request(self, req, cat, page, path_info):
        from bitten.master import BuildMaster
        master = BuildMaster(self.env)

        if req.method == 'POST':
            changed = False
            build_all = 'build_all' in req.args
            if build_all != master.build_all:
                self.config['bitten'].set('build_all',
                                          build_all and 'yes' or 'no')
                changed = True
            adjust_timestamps = 'adjust_timestamps' in req.args
            if adjust_timestamps != master.adjust_timestamps:
                self.config['bitten'].set('adjust_timestamps',
                                          adjust_timestamps and 'yes' or 'no')
                changed = True
            slave_timeout = int(req.args.get('slave_timeout', 0))
            if slave_timeout != master.slave_timeout:
                self.config['bitten'].set('slave_timeout', str(slave_timeout))
                changed = True
            if changed:
                self.config.save()

        req.hdf['admin.master'] = {
            'build_all': master.build_all,
            'adjust_timestamps': master.adjust_timestamps,
            'slave_timeout': master.slave_timeout,
        }
        return 'bitten_admin_master.cs', None


class BuildConfigurationsAdminPageProvider(Component):
    """Web administration panel for configuring the build master."""

    implements(IAdminPageProvider)

    # IAdminPageProvider methods

    def get_admin_pages(self, req):
        if req.perm.has_permission('BUILD_MODIFY'):
            yield ('bitten', 'Bitten', 'configs', 'Configurations')

    def process_admin_request(self, req, cat, page, config_name):
        data = {}

        if config_name:
            config = BuildConfig.fetch(self.env, config_name)
            platforms = list(TargetPlatform.select(self.env, config=config.name))

            if req.method == 'POST':
                if 'save' in req.args:
                    name = req.args.get('name')
                    if not name:
                        raise TracError('Missing required field "name"',
                                        'Missing field')
                    if not re.match(r'^[\w.-]+$', name):
                        raise TracError('The field "name" may only contain '
                                        'letters, digits, periods, or dashes.',
                                        'Invalid field')

                    path = req.args.get('path', '')
                    repos = self.env.get_repository(req.authname)
                    max_rev = req.args.get('max_rev') or None
                    try:
                        node = repos.get_node(path, max_rev)
                        assert node.isdir, '%s is not a directory' % node.path
                    except (AssertionError, TracError), e:
                        raise TracError(e, 'Invalid repository path')
                    if req.args.get('min_rev'):
                        try:
                            repos.get_node(path, req.args.get('min_rev'))
                        except TracError, e:
                            raise TracError(e,
                                            'Invalid value for oldest revision')

                    recipe_xml = req.args.get('recipe', '')
                    if recipe_xml:
                        try:
                            Recipe(xmlio.parse(recipe_xml)).validate()
                        except xmlio.ParseError, e:
                            raise TracError('Failure parsing recipe: %s' % e,
                                            'Invalid recipe')
                        except InvalidRecipeError, e:
                            raise TracError(e, 'Invalid recipe')

                    config.name = name
                    config.path = repos.normalize_path(path)
                    config.recipe = recipe_xml
                    config.min_rev = req.args.get('min_rev')
                    config.max_rev = req.args.get('max_rev')
                    config.label = req.args.get('label', '')
                    config.description = req.args.get('description', '')
                    config.update()
                    req.redirect(self.env.href.admin(cat, page))

                elif 'cancel' in req.args:
                    req.redirect(self.env.href.admin(cat, page))

            data['config'] = {
                'name': config.name, 'label': config.label or config.name,
                'active': config.active, 'path': config.path,
                'min_rev': config.min_rev, 'max_rev': config.max_rev,
                'description': config.description,
                'recipe': config.recipe,
                'platforms': [{
                    'name': platform.name,
                    'id': platform.id,
                    'href': req.href.admin('bitten', 'configs', config.name,
                                           platform.id)
                } for platform in platforms]
            }

        else:
            if req.method == 'POST':
                # Add configuration
                if 'add' in req.args:
                    config = BuildConfig(self.env)
                    config.name = req.args.get('name')
                    config.label = req.args.get('label', config.name)
                    config.path = req.args.get('path')
                    config.insert()
                    req.redirect(self.env.href.admin(cat, page, config.name))

                # Remove configurations
                elif 'remove' in req.args:
                    sel = req.args.get('sel')
                    sel = isinstance(sel, list) and sel or [sel]
                    if not sel:
                        raise TracError('No configuration selected')
                    db = self.env.get_db_cnx()
                    for name in sel:
                        config = BuildConfig.fetch(self.env, name, db=db)
                        config.delete(db=db)
                    db.commit()
                    req.redirect(self.env.href.admin(cat, page))

                # Set active state
                elif 'apply' in req.args:
                    active = req.args.get('active')
                    active = isinstance(active, list) and active or [active]
                    db = self.env.get_db_cnx()
                    for config in BuildConfig.select(self.env, db=db,
                                                     include_inactive=True):
                        config.active = config.name in active
                        config.update(db=db)
                    db.commit()
                    req.redirect(self.env.href.admin(cat, page))

            configs = []
            for config in BuildConfig.select(self.env, include_inactive=True):
                configs.append({
                    'name': config.name, 'label': config.label or config.name,
                    'active': config.active, 'path': config.path,
                    'min_rev': config.min_rev, 'max_rev': config.max_rev,
                    'href': req.href.admin('bitten', 'configs', config.name),
                })
            data['configs'] = configs

        req.hdf['admin'] = data
        return 'bitten_admin_configs.cs', None
