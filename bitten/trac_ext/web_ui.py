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
from trac.web.chrome import INavigationContributor
from trac.web.main import IRequestHandler
from trac.wiki import wiki_to_html
from bitten.model import Build, BuildConfig, SlaveInfo


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
     <input type="submit" value="Add new configuration" />
    </div></form><?cs
   /if ?></div><?cs

  elif:build.mode == 'edit_config' ?>
   <form method="post" action="">
    <div class="field"><label>Name:<br />
     <input type="text" name="name" value="<?cs var:build.config.name ?>" />
    </label></div>
    <div class="field"><label>Label (for display):<br />
     <input type="text" name="label" size="32" value="<?cs
       var:build.config.label ?>" />
    </label></div>
    <div class="field"><label><input type="checkbox" name="active"<?cs
      if:build.config.active ?> checked="checked" <?cs /if ?>/> Active
    </label></div>
    <div class="field"><label>Repository path:<br />
     <input type="text" name="path" size="48" value="<?cs
       var:build.config.path ?>" />
    </label></div>
    <div class="field"><fieldset class="iefix">
     <label for="description">Description (you may use <a tabindex="42" href="<?cs
       var:trac.href.wiki ?>/WikiFormatting">WikiFormatting</a> here):</label>
     <p><textarea id="description" name="description" class="wikitext" rows="10" cols="78"><?cs
       var:build.config.description ?></textarea></p>
     <script type="text/javascript" src="<?cs
       var:htdocs_location ?>js/wikitoolbar.js"></script>
    </fieldset></div>
    <div class="buttons">
     <input type="hidden" name="action" value="<?cs
       if:build.config.exists ?>edit<?cs else ?>new<?cs /if ?>" />
     <input type="submit" name="cancel" value="Cancel" />
     <input type="submit" value="<?cs
       if:build.config.exists ?>Save changes<?cs else ?>Create<?cs /if ?>" />
    </div>
   </form><?cs

  elif:build.mode == 'view_config' ?><ul>
   <li>Active: <?cs if:build.config.active ?>yes<?cs else ?>no<?cs /if ?></li>
   <li>Path: <?cs if:build.config.path ?><a href="<?cs
     var:build.config.browser_href ?>"><?cs
     var:build.config.path ?></a></li><?cs /if ?></ul><?cs
   if:build.config.description ?><div class="description"><?cs
     var:build.config.description ?></div><?cs /if ?><?cs
   if:build.can_modify ?><div class="buttons">
    <form method="get" action=""><div>
     <input type="hidden" name="action" value="edit" />
     <input type="submit" value="Edit configuration" />
    </div></form><?cs
   /if ?></div><?cs

  elif:build.mode == 'view_build' ?>
   <p class="trigger">Triggered by: Changeset <a href="<?cs
     var:build.chgset_href ?>">[<?cs var:build.rev ?>]</a> of <a href="<?cs
     var:build.config.href ?>"><?cs var:build.config.name ?></a></p>
   <p class="slave">Built by: <strong><?cs
     var:build.slave.name ?></strong> (<?cs var:build.slave.os ?> <?cs
     var:build.slave.os.version ?> on <?cs var:build.slave.machine ?>)</p>
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
        match = re.match(r'/build(?:/([\w.-]+))?(?:/([\w.-]+))?', req.path_info)
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
            if not config and action == 'new':
                self._do_create(req)
            elif config and action == 'edit':
                self._do_save(req, config)
        else:
            if not config:
                if action == 'new':
                    self._render_config_form(req)
                else:
                    self._render_overview(req)
            elif not id:
                if action == 'edit':
                    self._render_config_form(req, config)
                else:
                    self._render_config(req, config)
            else:
                self._render_build(req, config, id)

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

    def _do_create(self, req):
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

    def _do_save(self, req, config_name):
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
        description = config.description
        if description:
            description = wiki_to_html(description, self.env, req)
        req.hdf['build.config'] = {
            'name': config.name, 'label': config.label, 'path': config.path,
            'active': config.active, 'description': description,
            'browser_href': self.env.href.browser(config.path)
        }

        req.hdf['build.mode'] = 'view_config'
        req.hdf['build.can_modify'] = req.perm.has_permission('BUILD_MODIFY')

    def _render_config_form(self, req, config_name=None):
        config = BuildConfig(self.env, config_name)
        if config.exists:
            req.perm.assert_permission('BUILD_MODIFY')
            req.hdf['title'] = 'Edit Build Configuration "%s"' \
                               % escape(config.label or config.name)
            req.hdf['build.config'] = {
                'name': config.name, 'label': config.label, 'path': config.path,
                'active': config.active, 'description': config.description,
                'exists': config.exists
            }
        else:
            req.perm.assert_permission('BUILD_CREATE')
            req.hdf['title'] = 'Create Build Configuration'
        req.hdf['build.mode'] = 'edit_config'

    def _render_build(self, req, config_name, build_id):
        build = Build(self.env, build_id)
        assert build.exists
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

        slave_info = SlaveInfo(self.env, build.id)
        req.hdf['build.slave'] = {
            'name': build.slave,
            'ip_address': slave_info.properties.get(SlaveInfo.IP_ADDRESS),
            'os': slave_info.properties.get(SlaveInfo.OS_NAME),
            'os.family': slave_info.properties.get(SlaveInfo.OS_FAMILY),
            'os.version': slave_info.properties.get(SlaveInfo.OS_VERSION),
            'machine': slave_info.properties.get(SlaveInfo.MACHINE),
            'processor': slave_info.properties.get(SlaveInfo.PROCESSOR)
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
        return hdf
