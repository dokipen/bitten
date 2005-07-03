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

import re
from time import localtime, strftime

from trac.core import *
from trac.Timeline import ITimelineEventProvider
from trac.util import escape, pretty_timedelta
from trac.web.chrome import INavigationContributor, add_link
from trac.web.main import IRequestHandler
from trac.wiki import wiki_to_html
from bitten.model import Build, BuildConfig, TargetPlatform


class BuildModule(Component):

    implements(INavigationContributor, IRequestHandler, ITimelineEventProvider)

    build_cs = """
<?cs include:"header.cs" ?>
 <div id="ctxtnav" class="nav"></div>
 <div id="content" class="build">
  <h1><?cs var:title ?></h1><?cs

  if:build.mode == 'overview' ?><?cs
   each:config = build.configs ?>
    <h2><a href="<?cs var:config.href ?>"><?cs var:config.label ?></a></h2><?cs
    if:config.description ?><div class="description"><?cs
     var:config.description ?></div><?cs
    /if ?><?cs
   /each ?><?cs
   if:build.can_create ?><div class="buttons">
    <form method="get" action=""><div>
     <input type="hidden" name="action" value="new" />
     <input type="submit" value="Add configuration" />
    </div></form></div><?cs
   /if ?></div><?cs

  elif:build.mode == 'edit_config' ?>
   <form class="config" method="post" action="">
    <table><tr>
     <td class="name"><label>Name:<br />
      <input type="text" name="name" value="<?cs var:build.config.name ?>" />
     </label></td>
     <td class="label"><label>Label (for display):<br />
      <input type="text" name="label" size="32" value="<?cs
        var:build.config.label ?>" />
     </label></td>
    </tr><tr>
     <td class="active"><label><input type="checkbox" name="active"<?cs
       if:build.config.active ?> checked="checked" <?cs /if ?>/> Active
     </label></td>
     <td class="path"><label>Repository path:<br />
      <input type="text" name="path" size="48" value="<?cs
        var:build.config.path ?>" />
     </label></td>
    </tr><tr>
     <td colspan="2"><fieldset class="iefix">
      <label for="description">Description (you may use <a tabindex="42" href="<?cs
        var:trac.href.wiki ?>/WikiFormatting">WikiFormatting</a> here):</label>
      <p><textarea id="description" name="description" class="wikitext" rows="5" cols="78"><?cs
        var:build.config.description ?></textarea></p>
      <script type="text/javascript" src="<?cs
        var:htdocs_location ?>js/wikitoolbar.js"></script>
     </fieldset></td>
    </tr></table>
    <div class="buttons">
     <input type="hidden" name="action" value="<?cs
       if:build.config.exists ?>edit<?cs else ?>new<?cs /if ?>" />
     <input type="submit" name="cancel" value="Cancel" />
     <input type="submit" value="<?cs
       if:build.config.exists ?>Save changes<?cs else ?>Create<?cs /if ?>" />
    </div>
   </form><?cs
   if:build.config.exists ?><div class="platforms">
    <h2>Target Platforms</h2><?cs
     if:len(build.platforms) ?><ul><?cs
      each:platform = build.platforms ?><li><a href="<?cs
       var:platform.href ?>"><?cs var:platform.name ?></a></li><?cs
      /each ?></ul><?cs
     /if ?>
    <div class="buttons">
     <form method="get" action=""><div>
      <input type="hidden" name="action" value="new" />
      <input type="submit" value="Add target platform" />
     </div></form>
    </div>
   </div><?cs
   /if ?><?cs

  elif:build.mode == 'view_config' ?><ul>
   <li>Active: <?cs if:build.config.active ?>yes<?cs else ?>no<?cs /if ?></li>
   <li>Path: <?cs if:build.config.path ?><a href="<?cs
     var:build.config.browser_href ?>"><?cs
     var:build.config.path ?></a></li><?cs /if ?></ul><?cs
   if:build.config.description ?><div class="description"><?cs
     var:build.config.description ?></div><?cs /if ?><?cs
   if:build.config.can_modify ?><div class="buttons">
    <form method="get" action=""><div>
     <input type="hidden" name="action" value="edit" />
     <input type="submit" value="Edit configuration" />
    </div></form><?cs
   /if ?></div><?cs

  elif:build.mode == 'edit_platform' ?>
   <form class="platform" method="post" action="">
    <div class="field"><label>Name:<br />
     <input type="text" name="name" value="<?cs var:build.platform.name ?>" />
    </label></div>
    <h2>Rules</h2>
    <table><thead><tr>
     <th>Property name</th><th>Match pattern</th>
    </tr></thead><tbody><?cs
     each:rule = build.platform.rules ?><tr>
      <td><input type="text" name="property_<?cs var:name(rule) ?>" value="<?cs
       var:rule.property ?>" /></td>
      <td><input type="text" name="pattern_<?cs var:name(rule) ?>" value="<?cs
       var:rule.pattern ?>" /></td>
      <td><input type="submit" name="rm_rule_<?cs
        var:name(rule) ?>" value="-" /><input type="submit" name="add_rule_<?cs
        var:name(rule) ?>" value="+" />
      </td>
     </tr><?cs /each ?>
    </tbody></table>
    <div class="buttons">
     <form method="get" action=""><div>
     <input type="hidden" name="action" value="<?cs
       if:build.platform.exists ?>edit<?cs else ?>new<?cs /if ?>" />
      <input type="hidden" name="platform" value="<?cs
       var:build.platform.id ?>" />
      <input type="submit" name="cancel" value="Cancel" />
      <input type="submit" value="<?cs
       if:build.platform.exists ?>Save changes<?cs else ?>Add platform<?cs
       /if ?>" />
     </div></form>
    </div>
   </form><?cs

  elif:build.mode == 'view_build' ?>
   <p class="trigger">Triggered by: Changeset <a href="<?cs
     var:build.chgset_href ?>">[<?cs var:build.rev ?>]</a> of <a href="<?cs
     var:build.config.href ?>"><?cs var:build.config.name ?></a></p>
   <p class="slave">Built by: <strong title="<?cs
     var:build.slave.ip_address ?>"><?cs var:build.slave.name ?></strong> (<?cs
     var:build.slave.os ?> <?cs var:build.slave.os.version ?><?cs
     if:build.slave.machien ?> on <?cs var:build.slave.machine ?><?cs
     /if ?>)</p>
   <p class="time">Completed: <?cs var:build.started ?> (<?cs
     var:build.started_delta ?> ago)<br />Took: <?cs var:build.duration ?></p><?cs
  /if ?>

 </div>
<?cs include:"footer.cs" ?>
"""

    _status_label = {Build.IN_PROGRESS: 'in progress',
                     Build.SUCCESS: 'completed',
                     Build.FAILURE: 'failed'}

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
                    platform_id = req.args.get('platform')
                    if platform_id:
                        if action == 'edit':
                            self._do_save_platform(req, config, platform_id)
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
                        platform = TargetPlatform(self.env, int(platform_id))
                        self._render_platform_form(req, platform)
                    else:
                        self._render_config_form(req, config)
                elif action == 'new':
                    platform = TargetPlatform(self.env)
                    platform.config = config
                    self._render_platform_form(req, platform)
                else:
                    self._render_config(req, config)
            else:
                if action == 'new':
                    self._render_config_form(req)
                else:
                    self._render_overview(req)

        return req.hdf.parse(self.build_cs), None

    # ITimelineEventProvider methods

    def get_timeline_filters(self, req):
        if req.perm.has_permission('BUILD_VIEW'):
            yield ('build', 'Builds')

    def get_timeline_events(self, req, start, stop, filters):
        if 'build' in filters:
            db = self.env.get_db_cnx()
            cursor = db.cursor()
            cursor.execute("SELECT id,config,label,rev,slave,stopped,status "
                           "FROM bitten_build "
                           "  INNER JOIN bitten_config ON (name=config) "
                           "WHERE stopped>=%s AND stopped<=%s "
                           "AND status IN (%s, %s) ORDER BY stopped",
                           (start, stop, Build.SUCCESS, Build.FAILURE))
            event_kinds = {Build.SUCCESS: 'successbuild',
                           Build.FAILURE: 'failedbuild'}
            for id, config, label, rev, slave, stopped, status in cursor:
                title = 'Build <em title="[%s] of %s">%s</em> by %s %s' \
                        % (escape(rev), escape(label), escape(id),
                           escape(slave), self._status_label[status])
                href = self.env.href.build(config, id)
                yield event_kinds[status], href, title, stopped, None, ''

    # Internal methods

    def _do_create_config(self, req):
        """Create a new build configuration."""
        req.perm.assert_permission('BUILD_CREATE')

        if 'cancel' in req.args.keys():
            req.redirect(self.env.href.build())

        config = BuildConfig(self.env)
        config.name = req.args.get('name')
        config.active = req.args.has_key('active')
        config.label = req.args.get('label', '')
        config.path = req.args.get('path', '')
        config.description = req.args.get('description', '')
        config.insert()

        req.redirect(self.env.href.build(config.name))

    def _do_save_config(self, req, config_name):
        """Save changes to a build configuration."""
        req.perm.assert_permission('BUILD_MODIFY')

        if 'cancel' in req.args.keys():
            req.redirect(self.env.href.build(config_name))

        config = BuildConfig(self.env, config_name)
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

        platform = TargetPlatform(self.env)
        platform.config = config_name
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

        platform.insert()

        req.redirect(self.env.href.build(config_name, action='edit'))

    def _do_save_platform(self, req, config_name, platform_id):
        """Save changes to a target platform."""
        req.perm.assert_permission('BUILD_MODIFY')

        if 'cancel' in req.args.keys():
            req.redirect(self.env.href.build(config_name, action='edit'))

        platform = TargetPlatform(self.env, platform_id)
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
        config = BuildConfig(self.env, config_name)
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

        repos = self.env.get_repository(req.authname)
        root = repos.get_node(config.path)
        num = 0
        for idx, (path, rev, chg) in enumerate(root.get_history()):
            prefix = 'build.config.builds.%d' % rev
            for build in Build.select(self.env, config=config.name, rev=rev):
                req.hdf[prefix + '.' + build.slave] = self._build_to_hdf(build)
            if idx > 5:
                break

    def _render_config_form(self, req, config_name=None):
        config = BuildConfig(self.env, config_name)
        if config.exists:
            req.perm.assert_permission('BUILD_MODIFY')
            req.hdf['build.config'] = {
                'name': config.name, 'label': config.label, 'path': config.path,
                'active': config.active, 'description': config.description,
                'exists': config.exists
            }

            if 'new' in req.args.keys() or 'platform' in req.args.keys():
                self._render_platform_form(req, config_name,
                                           req.args.get('platform'))
                return

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
        req.hdf['title'] = 'Edit Target Platform "%s"' \
                           % escape(platform.name)
        req.hdf['build.platform'] = {
            'name': platform.name, 'id': platform.id, 'exists': platform.exists,
            'rules': [{'property': propname, 'pattern': pattern}
                      for propname, pattern in platform.rules]
        }
        req.hdf['build.mode'] = 'edit_platform'

    def _render_build(self, req, build_id):
        build = Build(self.env, build_id)
        assert build.exists
        add_link(req, 'up', self.env.href.build(build.config),
                 'Build Configuration')
        status2title = {Build.SUCCESS: 'Success', Build.FAILURE: 'Failure'}
        req.hdf['title'] = 'Build %s - %s' % (build_id,
                                              status2title[build.status])
        req.hdf['build'] = self._build_to_hdf(build)
        req.hdf['build.mode'] = 'view_build'

        config = BuildConfig(self.env, build.config)
        req.hdf['build.config'] = {
            'name': config.label,
            'href': self.env.href.build(config.name)
        }

    def _build_to_hdf(self, build):
        hdf = {'name': build.slave, 'status': self._status_label[build.status],
               'rev': build.rev,
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
        return hdf
