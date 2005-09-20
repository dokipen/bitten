# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import re
from time import localtime, strftime

import pkg_resources
from trac.core import *
from trac.Timeline import ITimelineEventProvider
from trac.util import escape, pretty_timedelta
from trac.web import IRequestHandler
from trac.web.chrome import INavigationContributor, ITemplateProvider, \
                            add_link, add_stylesheet
from trac.wiki import wiki_to_html
from bitten.model import BuildConfig, TargetPlatform, Build, BuildStep, \
                         BuildLog, Report
from bitten.trac_ext.api import ILogFormatter, IReportSummarizer

_status_label = {Build.IN_PROGRESS: 'in progress',
                 Build.SUCCESS: 'completed',
                 Build.FAILURE: 'failed'}

def _build_to_hdf(env, req, build):
    hdf = {'id': build.id, 'name': build.slave, 'rev': build.rev,
           'status': _status_label[build.status],
           'cls': _status_label[build.status].replace(' ', '-'),
           'href': env.href.build(build.config, build.id),
           'chgset_href': env.href.changeset(build.rev)}
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

class BittenChrome(Component):
    """Provides the Bitten templates and static resources."""

    implements(ITemplateProvider)

    # ITemplatesProvider methods

    def get_htdocs_dirs(self):
        return [('bitten', pkg_resources.resource_filename(__name__, 'htdocs'))]

    def get_templates_dirs(self):
        return [pkg_resources.resource_filename(__name__, 'templates')]


class BuildConfigController(Component):
    """Implements the web interface for build configurations."""

    implements(INavigationContributor, IRequestHandler)

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
        match = re.match(r'/build(?:/([\w.-]+))?/?$', req.path_info)
        if match:
            if match.group(1):
                req.args['config'] = match.group(1)
            return True

    def process_request(self, req):
        req.perm.assert_permission('BUILD_VIEW')

        action = req.args.get('action')
        config = req.args.get('config')

        if req.method == 'POST':
            if config:
                if action == 'new':
                    self._do_create_platform(req, config)
                elif action == 'delete':
                    self._do_delete_config(req, config)
                else:
                    platform_id = req.args.get('platform')
                    if platform_id:
                        if action == 'edit':
                            self._do_save_platform(req, config, platform_id)
                    elif 'delete' in req.args:
                        self._do_delete_platforms(req)
                        self._render_config_form(req, config)
                    elif 'new' in req.args:
                        platform = TargetPlatform(self.env, config=config)
                        self._render_platform_form(req, platform)
                    else:
                        self._do_save_config(req, config)
            else:
                if action == 'new':
                    self._do_create_config(req)
        else:
            if config:
                if action == 'delete':
                    self._render_config_confirm(req, config)
                elif action == 'edit':
                    platform_id = req.args.get('platform')
                    if platform_id:
                        platform = TargetPlatform.fetch(self.env,
                                                        int(platform_id))
                        self._render_platform_form(req, platform)
                    elif 'new' in req.args:
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

        add_stylesheet(req, 'bitten/bitten.css')
        return 'bitten_config.cs', None

    # Internal methods

    def _do_create_config(self, req):
        """Create a new build configuration."""
        req.perm.assert_permission('BUILD_CREATE')

        if 'cancel' in req.args:
            req.redirect(self.env.href.build())

        config_name = req.args.get('name')

        assert not BuildConfig.fetch(self.env, config_name), \
            'A build configuration with the name "%s" already exists' \
            % config_name

        config = BuildConfig(self.env, name=config_name,
                             path=req.args.get('path', ''),
                             recipe=req.args.get('recipe', ''),
                             min_rev=req.args.get('min_rev', ''),
                             max_rev=req.args.get('max_rev', ''),
                             label=req.args.get('label', ''),
                             description=req.args.get('description'))
        config.insert()

        req.redirect(self.env.href.build(config.name))

    def _do_delete_config(self, req, config_name):
        """Save changes to a build configuration."""
        req.perm.assert_permission('BUILD_DELETE')

        if 'cancel' in req.args:
            req.redirect(self.env.href.build(config_name))

        db = self.env.get_db_cnx()

        config = BuildConfig.fetch(self.env, config_name, db=db)
        assert config, 'Build configuration "%s" does not exist' % config_name

        config.delete(db=db)

        db.commit()

        req.redirect(self.env.href.build())

    def _do_save_config(self, req, config_name):
        """Save changes to a build configuration."""
        req.perm.assert_permission('BUILD_MODIFY')

        if 'cancel' in req.args:
            req.redirect(self.env.href.build(config_name))

        config = BuildConfig.fetch(self.env, config_name)
        assert config, 'Build configuration "%s" does not exist' % config_name

        if 'activate' in req.args:
            config.active = True

        elif 'deactivate' in req.args:
            config.active = False

        else:
            # TODO: Validate recipe, repository path, etc
            config.name = req.args.get('name')
            config.path = req.args.get('path', '')
            config.recipe = req.args.get('recipe', '')
            config.min_rev = req.args.get('min_rev')
            config.max_rev = req.args.get('max_rev')
            config.label = req.args.get('label', '')
            config.description = req.args.get('description', '')

        config.update()
        req.redirect(self.env.href.build(config.name))

    def _do_create_platform(self, req, config_name):
        """Create a new target platform."""
        req.perm.assert_permission('BUILD_MODIFY')

        if 'cancel' in req.args:
            req.redirect(self.env.href.build(config_name, action='edit'))

        platform = TargetPlatform(self.env, config=config_name)
        if self._process_platform(req, platform):
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

            # FIXME: this should probably also delete all builds done for this
            # platform, and all the associated reports

        db.commit()

    def _do_save_platform(self, req, config_name, platform_id):
        """Save changes to a target platform."""
        req.perm.assert_permission('BUILD_MODIFY')

        if 'cancel' in req.args:
            req.redirect(self.env.href.build(config_name, action='edit'))

        platform = TargetPlatform.fetch(self.env, platform_id)
        if self._process_platform(req, platform):
            platform.update()
            req.redirect(self.env.href.build(config_name, action='edit'))

    def _process_platform(self, req, platform):
        platform.name = req.args.get('name')

        properties = [int(key[9:]) for key in req.args.keys()
                      if key.startswith('property_')]
        properties.sort()
        patterns = [int(key[8:]) for key in req.args.keys()
                    if key.startswith('pattern_')]
        patterns.sort()
        platform.rules = [(req.args.get('property_%d' % property),
                           req.args.get('pattern_%d' % pattern))
                          for property, pattern in zip(properties, patterns)
                          if req.args.get('property_%d' % property)]

        add_rules = [int(key[9:]) for key in req.args.keys()
                     if key.startswith('add_rule_')]
        if add_rules:
            platform.rules.insert(add_rules[0] + 1, ('', ''))
            self._render_platform_form(req, platform)
            return False
        rm_rules = [int(key[8:]) for key in req.args.keys()
                    if key.startswith('rm_rule_')]
        if rm_rules:
            del platform.rules[rm_rules[0]]
            self._render_platform_form(req, platform)
            return False

        return True

    def _render_overview(self, req):
        req.hdf['title'] = 'Build Status'
        show_all = False
        if req.args.get('show') == 'all':
            show_all = True
        req.hdf['config.show_all'] = show_all

        configurations = BuildConfig.select(self.env, include_inactive=show_all)
        for idx, config in enumerate(configurations):
            description = config.description
            if description:
                description = wiki_to_html(description, self.env, req)
            req.hdf['configs.%d' % idx] = {
                'name': config.name, 'label': config.label or config.name,
                'active': config.active, 'path': config.path,
                'description': description,
                'href': self.env.href.build(config.name),
            }
        req.hdf['page.mode'] = 'overview'
        req.hdf['config.can_create'] = req.perm.has_permission('BUILD_CREATE')

    def _render_config(self, req, config_name):
        config = BuildConfig.fetch(self.env, config_name)
        req.hdf['title'] = 'Build Configuration "%s"' \
                           % escape(config.label or config.name)
        add_link(req, 'up', self.env.href.build(), 'Build Status')
        description = config.description
        if description:
            description = wiki_to_html(description, self.env, req)
        req.hdf['config'] = {
            'name': config.name, 'label': config.label, 'path': config.path,
            'active': config.active, 'description': description,
            'browser_href': self.env.href.browser(config.path),
            'can_modify': req.perm.has_permission('BUILD_MODIFY'),
            'can_delete': req.perm.has_permission('BUILD_DELETE')
        }
        req.hdf['page.mode'] = 'view_config'

        platforms = TargetPlatform.select(self.env, config=config_name)
        req.hdf['config.platforms'] = [
            {'name': platform.name, 'id': platform.id} for platform in platforms
        ]

        has_reports = False
        for report in Report.select(self.env, config=config.name):
            has_reports = True
            break

        if has_reports:
            req.hdf['config.charts'] = [
                {'href': self.env.href.build(config.name, 'chart/test')},
                {'href': self.env.href.build(config.name, 'chart/coverage')}
            ]
            charts_license = self.config.get('bitten', 'charts_license')
            if charts_license:
                req.hdf['config.charts_license'] = escape(charts_license)

        repos = self.env.get_repository(req.authname)
        try:
            root = repos.get_node(config.path)
            for idx, (path, rev, chg) in enumerate(root.get_history()):
                # Don't follow moves/copies
                if path != repos.normalize_path(config.path):
                    break
                # If the directory was empty at that revision, it isn't built
                old_node = repos.get_node(path, rev)
                is_empty = True
                for entry in old_node.get_entries():
                    is_empty = False
                    break
                if is_empty:
                    continue

                prefix = 'config.builds.%d' % rev
                req.hdf[prefix + '.href'] = self.env.href.changeset(rev)
                for build in Build.select(self.env, config=config.name, rev=rev):
                    if build.status == Build.PENDING:
                        continue
                    build_hdf = _build_to_hdf(self.env, req, build)
                    req.hdf['%s.%s' % (prefix, build.platform)] = build_hdf
                if idx > 12:
                    break
        except TracError, e:
            self.log.error('Error accessing repository info', exc_info=True)

    def _render_config_confirm(self, req, config_name):
        req.perm.assert_permission('BUILD_DELETE')
        config = BuildConfig.fetch(self.env, config_name)
        req.hdf['title'] = 'Delete Build Configuration "%s"' \
                           % escape(config.label or config.name)
        req.hdf['config'] = {'name': config.name}
        req.hdf['page.mode'] = 'delete_config'

    def _render_config_form(self, req, config_name=None):
        config = BuildConfig.fetch(self.env, config_name)
        if config:
            req.perm.assert_permission('BUILD_MODIFY')
            req.hdf['config'] = {
                'name': config.name, 'exists': config.exists,
                'path': config.path, 'active': config.active,
                'recipe': config.recipe, 'min_rev': config.min_rev,
                'max_rev': config.max_rev, 'label': config.label,
                'description': config.description
            }

            req.hdf['title'] = 'Edit Build Configuration "%s"' \
                               % escape(config.label or config.name)
            for idx, platform in enumerate(TargetPlatform.select(self.env,
                                                                 config_name)):
                req.hdf['config.platforms.%d' % idx] = {
                    'id': platform.id, 'name': platform.name,
                    'href': self.env.href.build(config_name, action='edit',
                                                platform=platform.id)
                }
        else:
            req.perm.assert_permission('BUILD_CREATE')
            req.hdf['title'] = 'Create Build Configuration'
        req.hdf['page.mode'] = 'edit_config'

    def _render_platform_form(self, req, platform):
        req.perm.assert_permission('BUILD_MODIFY')
        if platform.exists:
            req.hdf['title'] = 'Edit Target Platform "%s"' \
                               % escape(platform.name)
        else:
            req.hdf['title'] = 'Add Target Platform'
        req.hdf['platform'] = {
            'name': platform.name, 'id': platform.id, 'exists': platform.exists,
            'rules': [{'property': propname, 'pattern': pattern}
                      for propname, pattern in platform.rules] or [('', '')]
        }
        req.hdf['page.mode'] = 'edit_platform'


class BuildController(Component):
    """Renders the build page."""
    implements(INavigationContributor, IRequestHandler, ITimelineEventProvider)

    log_formatters = ExtensionPoint(ILogFormatter)
    report_summarizers = ExtensionPoint(IReportSummarizer)

    # INavigationContributor methods

    def get_active_navigation_item(self, req):
        return 'build'

    def get_navigation_items(self, req):
        return []

    # IRequestHandler methods

    def match_request(self, req):
        match = re.match(r'/build/([\w.-]+)/(\d+)', req.path_info)
        if match:
            if match.group(1):
                req.args['config'] = match.group(1)
                if match.group(2):
                    req.args['id'] = match.group(2)
            return True

    def process_request(self, req):
        req.perm.assert_permission('BUILD_VIEW')

        db = self.env.get_db_cnx()
        build_id = int(req.args.get('id'))
        build = Build.fetch(self.env, build_id, db=db)
        assert build, 'Build %s does not exist' % build_id

        if req.method == 'POST':
            if req.args.get('action') == 'invalidate':
                self._do_invalidate(req, build, db)
            req.redirect(self.env.href.build(build.config, build.id))

        add_link(req, 'up', self.env.href.build(build.config),
                 'Build Configuration')
        status2title = {Build.SUCCESS: 'Success', Build.FAILURE: 'Failure',
                        Build.IN_PROGRESS: 'In Progress'}
        req.hdf['title'] = 'Build %s - %s' % (build_id,
                                              status2title[build.status])
        req.hdf['page.mode'] = 'view_build'
        config = BuildConfig.fetch(self.env, build.config, db=db)
        req.hdf['build.config'] = {
            'name': config.label,
            'href': self.env.href.build(config.name)
        }

        req.hdf['build'] = _build_to_hdf(self.env, req, build)
        steps = []
        for step in BuildStep.select(self.env, build=build.id, db=db):
            steps.append({
                'name': step.name, 'description': step.description,
                'duration': pretty_timedelta(step.started, step.stopped),
                'failed': step.status == BuildStep.FAILURE,
                'log': self._render_log(req, build, step),
                'reports': self._render_reports(req, config, build, step)
            })
        req.hdf['build.steps'] = steps
        req.hdf['build.can_delete'] = req.perm.has_permission('BUILD_DELETE')

        add_stylesheet(req, 'bitten/bitten.css')
        return 'bitten_build.cs', None

    # ITimelineEventProvider methods

    def get_timeline_filters(self, req):
        if req.perm.has_permission('BUILD_VIEW'):
            yield ('build', 'Builds')

    def get_timeline_events(self, req, start, stop, filters):
        if 'build' in filters:
            add_stylesheet(req, 'bitten/bitten.css')
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
                title = 'Build of <em>%s [%s]</em> on %s %s' \
                        % (escape(label), escape(rev), escape(platform),
                           _status_label[status])
                if req.args.get('format') == 'rss':
                    href = self.env.abs_href.build(config, id)
                else:
                    href = self.env.href.build(config, id)
                yield event_kinds[status], href, title, stopped, None, ''

    # Internal methods

    def _do_invalidate(self, req, build, db):
        self.log.info('Invalidating build %d', build.id)

        for step in BuildStep.select(self.env, build=build.id, db=db):
            step.delete(db=db)

        build.slave = None
        build.started = build.stopped = 0
        build.status = Build.PENDING
        build.slave_info = {}
        build.update()

        db.commit()

        req.redirect(self.env.href.build(build.config))

    def _render_log(self, req, build, step):
        items = []
        for log in BuildLog.select(self.env, build=build.id, step=step.name):
            formatters = []
            for formatter in self.log_formatters:
                formatters.append(formatter.get_formatter(req, build, step,
                                                          log.generator))
            for level, message in log.messages:
                for format in formatters:
                    message = format(level, message)
                items.append({'level': level, 'message': message})
        return items

    def _render_reports(self, req, config, build, step):
        summarizers = {} # keyed by report type
        for summarizer in self.report_summarizers:
            categories = summarizer.get_supported_categories()
            summarizers.update(dict([(cat, summarizer) for cat in categories]))

        reports = []
        for report in Report.select(self.env, build=build.id, step=step.name):
            summarizer = summarizers.get(report.category)
            if summarizer:
                summary = summarizer.render_summary(req, config, build, step,
                                                    report.category)
            else:
                summary = None
            reports.append({'category': report.category, 'summary': summary})
        return reports


class SourceFileLinkFormatter(Component):
    """Finds references to files and directories in the repository in the build
    log and renders them as links to the repository browser."""

    implements(ILogFormatter)

    def get_formatter(self, req, build, step, type):
        config = BuildConfig.fetch(self.env, build.config)
        repos = self.env.get_repository(req.authname)
        nodes = []
        def _walk(node):
            for child in node.get_entries():
                path = child.path[len(config.path) + 1:]
                pattern = re.compile("([\s'\"])(%s|%s)([\s'\"])"
                                     % (re.escape(path),
                                        re.escape(path.replace('/', '\\'))))
                nodes.append((child.path, pattern))
                if child.isdir:
                    _walk(child)
        _walk(repos.get_node(config.path, build.rev))
        nodes.sort(lambda x, y: -cmp(len(x[0]), len(y[0])))

        def _formatter(level, message):
            for path, pattern in nodes:
                def _replace(m):
                    return '%s<a href="%s">%s</a>%s' % (m.group(1),
                           self.env.href.browser(path, rev=build.rev),
                           m.group(2), m.group(3))
                message = pattern.sub(_replace, message)
            return message
        return _formatter
