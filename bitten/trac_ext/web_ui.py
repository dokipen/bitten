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

import os.path
import re
import sys
from time import localtime, strftime

from trac.core import *
from trac.Timeline import ITimelineEventProvider
from trac.util import escape, pretty_timedelta
from trac.web.chrome import INavigationContributor, ITemplateProvider, \
                            add_link, add_stylesheet
from trac.web.main import IRequestHandler
from trac.wiki import wiki_to_html
from bitten.model import BuildConfig, TargetPlatform, Build, BuildStep

def _find_dir(name):
    import bitten
    # First assume we're being executing directly form the source directory
    path = os.path.join(os.path.split(os.path.dirname(bitten.__file__))[0],
                        name)
    if not os.path.isdir(path):
        # Not being executed from the source directory, so assume the
        # default installation prefix
        path = os.path.join(sys.prefix, 'share', 'bitten', name)
    return path


class BuildModule(Component):
    """Implements the Bitten web interface."""

    implements(INavigationContributor, IRequestHandler, ITimelineEventProvider,
               ITemplateProvider)

    _status_label = {Build.IN_PROGRESS: 'in progress',
                     Build.SUCCESS: 'completed',
                     Build.FAILURE: 'failed'}

    htdocs_dir = _find_dir('htdocs')
    templates_dir = _find_dir('templates')

    # INavigationContributor methods

    def get_active_navigation_item(self, req):
        return 'build'

    def get_navigation_items(self, req):
        if not req.perm.has_permission('BUILD_VIEW'):
            return
        yield 'mainnav', 'build', \
              '<a href="%s" accesskey="5">Build Status</a>' \
              % self.env.href.build()

    # IRequestHandler methods

    def match_request(self, req):
        match = re.match(r'/build(?:/([\w.-]+))?(?:/([\d]+))?', req.path_info)
        if match:
            if match.group(1):
                req.args['config'] = match.group(1)
                if match.group(2):
                    req.args['id'] = match.group(2)
            return True

    def process_request(self, req):
        req.perm.assert_permission('BUILD_VIEW')

        action = req.args.get('action')
        config = req.args.get('config')
        id = req.args.get('id')

        if req.method == 'POST':
            if config:
                if action == 'new':
                    self._do_create_platform(req, config)
                else:
                    self.log.debug('Request args: %s', req.args.keys())
                    platform_id = req.args.get('platform')
                    if platform_id:
                        if action == 'edit':
                            self._do_save_platform(req, config, platform_id)
                    elif 'delete' in req.args.keys():
                        self._do_delete_platforms(req)
                        self._render_config_form(req, config)
                    elif 'new' in req.args.keys():
                        platform = TargetPlatform(self.env, config=config)
                        self._render_platform_form(req, platform)
                    else:
                        self._do_save_config(req, config)
            else:
                if action == 'new':
                    self._do_create_config(req)
        else:
            if id:
                self._render_build(req, id)
            elif config:
                if action == 'edit':
                    platform_id = req.args.get('platform')
                    if platform_id:
                        platform = TargetPlatform.fetch(self.env,
                                                        int(platform_id))
                        self._render_platform_form(req, platform)
                    elif 'new' in req.args.keys():
                        platform = TargetPlatform(self.env, config=config)
                        self._render_platform_form(req, platform)
                    else:
                        self._render_config_form(req, config)
                else:
                    self._render_config(req, config)
            else:
                if action == 'new':
                    self._render_config_form(req)
                else:
                    self._render_overview(req)

        add_stylesheet(req, 'build.css')
        return 'build.cs', None

    # ITemplatesProvider methods

    def get_htdocs_dir(self):
        return self.config.get('bitten', 'htdocs_dir') or self.htdocs_dir

    def get_templates_dir(self):
        return self.config.get('bitten', 'templates_dir') or self.templates_dir

    # ITimelineEventProvider methods

    def get_timeline_filters(self, req):
        if req.perm.has_permission('BUILD_VIEW'):
            yield ('build', 'Builds')

    def get_timeline_events(self, req, start, stop, filters):
        if 'build' in filters:
            add_stylesheet(req, 'build.css')
            db = self.env.get_db_cnx()
            cursor = db.cursor()
            cursor.execute("SELECT b.id,b.config,c.label,b.rev,p.name,b.slave,"
                           "b.stopped,b.status FROM bitten_build AS b"
                           "  INNER JOIN bitten_config AS c ON (c.name=b.config)"
                           "  INNER JOIN bitten_platform AS p ON (p.id=b.platform) "
                           "WHERE b.stopped>=%s AND b.stopped<=%s "
                           "AND b.status IN (%s, %s) ORDER BY b.stopped",
                           (start, stop, Build.SUCCESS, Build.FAILURE))
            event_kinds = {Build.SUCCESS: 'successbuild',
                           Build.FAILURE: 'failedbuild'}
            for id, config, label, rev, platform, slave, stopped, status in cursor:
                title = 'Build of <em>%s [%s]</em> by %s (%s) %s' \
                        % (escape(label), escape(rev), escape(slave),
                           escape(platform), self._status_label[status])
                if req.args.get('format') == 'rss':
                    href = self.env.abs_href.build(config, id)
                else:
                    href = self.env.href.build(config, id)
                yield event_kinds[status], href, title, stopped, None, ''

    # Internal methods

    def _do_create_config(self, req):
        """Create a new build configuration."""
        req.perm.assert_permission('BUILD_CREATE')

        if 'cancel' in req.args.keys():
            req.redirect(self.env.href.build())

        config = BuildConfig(self.env, name=req.args.get('name'),
                             path=req.args.get('path', ''),
                             label=req.args.get('label', ''),
                             active=req.args.has_key('active'),
                             description=req.args.get('description'))
        config.insert()

        req.redirect(self.env.href.build(config.name))

    def _do_save_config(self, req, config_name):
        """Save changes to a build configuration."""
        req.perm.assert_permission('BUILD_MODIFY')

        if 'cancel' in req.args.keys():
            req.redirect(self.env.href.build(config_name))

        config = BuildConfig.fetch(self.env, config_name)
        assert config, 'Build configuration "%s" does not exist' % config_name
        config.name = req.args.get('name')
        config.active = req.args.has_key('active')
        config.label = req.args.get('label', '')
        config.path = req.args.get('path', '')
        config.description = req.args.get('description', '')
        config.update()

        req.redirect(self.env.href.build(config.name))

    def _do_create_platform(self, req, config_name):
        """Create a new target platform."""
        req.perm.assert_permission('BUILD_MODIFY')

        if 'cancel' in req.args.keys():
            req.redirect(self.env.href.build(config_name, action='edit'))

        platform = TargetPlatform(self.env, config=config_name,
                                  name=req.args.get('name'))

        properties = [int(key[9:]) for key in req.args.keys()
                      if key.startswith('property_')]
        properties.sort()
        patterns = [int(key[8:]) for key in req.args.keys()
                    if key.startswith('pattern_')]
        patterns.sort()
        platform.rules = [(req.args.get('property_%d' % property),
                           req.args.get('pattern_%d' % pattern))
                          for property, pattern in zip(properties, patterns)]

        add_rules = [int(key[9:]) for key in req.args.keys()
                     if key.startswith('add_rule_')]
        if add_rules:
            platform.rules.insert(add_rules[0] + 1, ('', ''))
            self._render_platform_form(req, platform)
            return
        rm_rules = [int(key[8:]) for key in req.args.keys()
                     if key.startswith('rm_rule_')]
        if rm_rules:
            del platform.rules[rm_rules[0]]
            self._render_platform_form(req, platform)
            return

        platform.insert()

        req.redirect(self.env.href.build(config_name, action='edit'))

    def _do_delete_platforms(self, req):
        """Delete selected target platforms."""
        req.perm.assert_permission('BUILD_MODIFY')
        self.log.debug('_do_delete_platforms')

        db = self.env.get_db_cnx()
        for platform_id in [int(id) for id in req.args.get('delete_platform')]:
            platform = TargetPlatform.fetch(self.env, platform_id, db=db)
            self.log.info('Deleting target platform %s of configuration %s',
                          platform.name, platform.config)
            platform.delete(db=db)
        db.commit()

    def _do_save_platform(self, req, config_name, platform_id):
        """Save changes to a target platform."""
        req.perm.assert_permission('BUILD_MODIFY')

        if 'cancel' in req.args.keys():
            req.redirect(self.env.href.build(config_name, action='edit'))

        platform = TargetPlatform.fetch(self.env, platform_id)
        platform.name = req.args.get('name')

        properties = [int(key[9:]) for key in req.args.keys()
                      if key.startswith('property_')]
        properties.sort()
        patterns = [int(key[8:]) for key in req.args.keys()
                    if key.startswith('pattern_')]
        patterns.sort()
        platform.rules = [(req.args.get('property_%d' % property),
                           req.args.get('pattern_%d' % pattern))
                          for property, pattern in zip(properties, patterns)]

        add_rules = [int(key[9:]) for key in req.args.keys()
                     if key.startswith('add_rule_')]
        if add_rules:
            platform.rules.insert(add_rules[0] + 1, ('', ''))
            self._render_platform_form(req, platform)
            return
        rm_rules = [int(key[8:]) for key in req.args.keys()
                     if key.startswith('rm_rule_')]
        if rm_rules:
            del platform.rules[rm_rules[0]]
            self._render_platform_form(req, platform)
            return

        platform.update()

        req.redirect(self.env.href.build(config_name, action='edit'))

    def _render_overview(self, req):
        req.hdf['title'] = 'Build Status'
        configurations = BuildConfig.select(self.env, include_inactive=True)
        for idx, config in enumerate(configurations):
            description = config.description
            if description:
                description = wiki_to_html(description, self.env, req)
            req.hdf['build.configs.%d' % idx] = {
                'name': config.name, 'label': config.label or config.name,
                'path': config.path, 'description': description,
                'href': self.env.href.build(config.name)
            }
        req.hdf['build.mode'] = 'overview'
        req.hdf['build.can_create'] = req.perm.has_permission('BUILD_CREATE')

    def _render_config(self, req, config_name):
        config = BuildConfig.fetch(self.env, config_name)
        req.hdf['title'] = 'Build Configuration "%s"' \
                           % escape(config.label or config.name)
        add_link(req, 'up', self.env.href.build(), 'Build Status')
        description = config.description
        if description:
            description = wiki_to_html(description, self.env, req)
        req.hdf['build.config'] = {
            'name': config.name, 'label': config.label, 'path': config.path,
            'active': config.active, 'description': description,
            'browser_href': self.env.href.browser(config.path),
            'can_modify': req.perm.has_permission('BUILD_MODIFY')
        }
        req.hdf['build.mode'] = 'view_config'

        platforms = TargetPlatform.select(self.env, config=config_name)
        req.hdf['build.platforms'] = [
            {'name': platform.name, 'id': platform.id} for platform in platforms
        ]

        repos = self.env.get_repository(req.authname)
        root = repos.get_node(config.path)
        num = 0
        for idx, (path, rev, chg) in enumerate(root.get_history()):
            prefix = 'build.builds.%d' % rev
            req.hdf[prefix + '.href'] = self.env.href.changeset(rev)
            for build in Build.select(self.env, config=config.name, rev=rev):
                if build.status == Build.PENDING:
                    continue
                req.hdf['%s.%s' % (prefix, build.platform)] = self._build_to_hdf(build)
            if idx > 4:
                break

    def _render_config_form(self, req, config_name=None):
        config = BuildConfig.fetch(self.env, config_name)
        if config:
            req.perm.assert_permission('BUILD_MODIFY')
            req.hdf['build.config'] = {
                'name': config.name, 'label': config.label, 'path': config.path,
                'active': config.active, 'description': config.description,
                'exists': config.exists
            }

            req.hdf['title'] = 'Edit Build Configuration "%s"' \
                               % escape(config.label or config.name)
            for idx, platform in enumerate(TargetPlatform.select(self.env,
                                                                 config_name)):
                req.hdf['build.platforms.%d' % idx] = {
                    'id': platform.id, 'name': platform.name,
                    'href': self.env.href.build(config_name, action='edit',
                                                platform=platform.id)
                }
        else:
            req.perm.assert_permission('BUILD_CREATE')
            req.hdf['title'] = 'Create Build Configuration'
        req.hdf['build.mode'] = 'edit_config'

    def _render_platform_form(self, req, platform):
        req.perm.assert_permission('BUILD_MODIFY')
        if platform.exists:
            req.hdf['title'] = 'Edit Target Platform "%s"' \
                               % escape(platform.name)
        else:
            req.hdf['title'] = 'Add Target Platform'
        req.hdf['build.platform'] = {
            'name': platform.name, 'id': platform.id, 'exists': platform.exists,
            'rules': [{'property': propname, 'pattern': pattern}
                      for propname, pattern in platform.rules] or [('', '')]
        }
        req.hdf['build.mode'] = 'edit_platform'

    def _render_build(self, req, build_id):
        build = Build.fetch(self.env, build_id)
        assert build, 'Build %s does not exist' % build_id
        add_link(req, 'up', self.env.href.build(build.config),
                 'Build Configuration')
        status2title = {Build.SUCCESS: 'Success', Build.FAILURE: 'Failure',
                        Build.IN_PROGRESS: 'In Progress'}
        req.hdf['title'] = 'Build %s - %s' % (build_id,
                                              status2title[build.status])
        req.hdf['build'] = self._build_to_hdf(build)
        req.hdf['build.mode'] = 'view_build'

        config = BuildConfig.fetch(self.env, build.config)
        req.hdf['build.config'] = {
            'name': config.label,
            'href': self.env.href.build(config.name)
        }

    def _build_to_hdf(self, build):
        hdf = {'id': build.id, 'name': build.slave, 'rev': build.rev,
               'status': self._status_label[build.status],
               'cls': self._status_label[build.status].replace(' ', '-'),
               'href': self.env.href.build(build.config, build.id),
               'chgset_href': self.env.href.changeset(build.rev)}
        if build.started:
            hdf['started'] = strftime('%x %X', localtime(build.started))
            hdf['started_delta'] = pretty_timedelta(build.started)
        if build.stopped:
            hdf['stopped'] = strftime('%x %X', localtime(build.stopped))
            hdf['stopped_delta'] = pretty_timedelta(build.stopped)
            hdf['duration'] = pretty_timedelta(build.stopped, build.started)
        hdf['slave'] = {
            'name': build.slave,
            'ip_address': build.slave_info.get(Build.IP_ADDRESS),
            'os': build.slave_info.get(Build.OS_NAME),
            'os.family': build.slave_info.get(Build.OS_FAMILY),
            'os.version': build.slave_info.get(Build.OS_VERSION),
            'machine': build.slave_info.get(Build.MACHINE),
            'processor': build.slave_info.get(Build.PROCESSOR)
        }
        steps = []
        for step in BuildStep.select(self.env, build=build.id):
            steps.append({
                'name': step.name, 'description': step.description,
                'duration': pretty_timedelta(step.started, step.stopped),
                'log': step.log
            })
        hdf['steps'] = steps

        return hdf
