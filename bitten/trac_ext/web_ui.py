# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

"""Implementation of the Bitten web interface."""

from datetime import datetime
import posixpath
import re
try:
    set
except NameError:
    from sets import Set as set
from StringIO import StringIO

import pkg_resources
from trac.core import *
try:
    from trac.timeline import ITimelineEventProvider
except ImportError:
    from trac.Timeline import ITimelineEventProvider
from trac.util import escape, pretty_timedelta, format_datetime, shorten_line, \
                      Markup
from trac.web import IRequestHandler
from trac.web.chrome import INavigationContributor, ITemplateProvider, \
                            add_link, add_stylesheet
from trac.wiki import wiki_to_html, wiki_to_oneliner
from bitten.model import BuildConfig, TargetPlatform, Build, BuildStep, \
                         BuildLog, Report
from bitten.queue import collect_changes
from bitten.recipe import Recipe, InvalidRecipeError
from bitten.trac_ext.api import ILogFormatter, IReportSummarizer
from bitten.util import xmlio

_status_label = {Build.PENDING: 'pending',
                 Build.IN_PROGRESS: 'in progress',
                 Build.SUCCESS: 'completed',
                 Build.FAILURE: 'failed'}

def _build_to_hdf(env, req, build):
    hdf = {'id': build.id, 'name': build.slave, 'rev': build.rev,
           'status': _status_label[build.status],
           'cls': _status_label[build.status].replace(' ', '-'),
           'href': env.href.build(build.config, build.id),
           'chgset_href': env.href.changeset(build.rev)}
    if build.started:
        hdf['started'] = format_datetime(build.started)
        hdf['started_delta'] = pretty_timedelta(build.started)
    if build.stopped:
        hdf['stopped'] = format_datetime(build.stopped)
        hdf['stopped_delta'] = pretty_timedelta(build.stopped)
        hdf['duration'] = pretty_timedelta(build.stopped, build.started)
    hdf['slave'] = {
        'name': build.slave,
        'ipnr': build.slave_info.get(Build.IP_ADDRESS),
        'os.name': build.slave_info.get(Build.OS_NAME),
        'os.family': build.slave_info.get(Build.OS_FAMILY),
        'os.version': build.slave_info.get(Build.OS_VERSION),
        'machine': build.slave_info.get(Build.MACHINE),
        'processor': build.slave_info.get(Build.PROCESSOR)
    }
    return hdf


class BittenChrome(Component):
    """Provides the Bitten templates and static resources."""

    implements(INavigationContributor, ITemplateProvider)

    # INavigationContributor methods

    def get_active_navigation_item(self, req):
        """Called by Trac to determine which navigation item should be marked
        as active.
        
        @param req: the request object
        """
        return 'build'

    def get_navigation_items(self, req):
        """Return the navigation item for access the build status overview from
        the Trac navigation bar."""
        if not req.perm.has_permission('BUILD_VIEW'):
            return
        yield ('mainnav', 'build', \
               Markup('<a href="%s" accesskey="5">Build Status</a>',
                      self.env.href.build()))

    # ITemplatesProvider methods

    def get_htdocs_dirs(self):
        """Return the directories containing static resources."""
        return [('bitten', pkg_resources.resource_filename(__name__, 'htdocs'))]

    def get_templates_dirs(self):
        """Return the directories containing templates."""
        return [pkg_resources.resource_filename(__name__, 'templates')]


class BuildConfigController(Component):
    """Implements the web interface for build configurations."""

    implements(IRequestHandler)

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

        if BuildConfig.fetch(self.env, config_name):
            raise TracError('A build configuration with the name "%s" already '
                            'exists' % config_name, 'Duplicate name')

        config = BuildConfig(self.env)
        self._process_config(req, config)
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
        if not config:
            # FIXME: 404
            raise TracError('Build configuration "%s" does not exist'
                            % config_name, 'Object not found')

        if 'activate' in req.args:
            config.active = True

        elif 'deactivate' in req.args:
            config.active = False

        else:
            self._process_config(req, config)

        config.update()
        req.redirect(self.env.href.build(config.name))

    def _process_config(self, req, config):
        name = req.args.get('name')
        if not name:
            raise TracError('Missing required field "name"', 'Missing field')
        if not re.match(r'^[\w.-]+$', name):
            raise TracError('The field "name" may only contain letters, '
                            'digits, periods, or dashes.', 'Invalid field')

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
                raise TracError(e, 'Invalid value for oldest revision')

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

        configs = BuildConfig.select(self.env, include_inactive=show_all)
        for idx, config in enumerate(configs):
            prefix = 'configs.%d' % idx
            description = config.description
            if description:
                description = wiki_to_html(description, self.env, req)
            req.hdf[prefix] = {
                'name': config.name, 'label': config.label or config.name,
                'active': config.active, 'path': config.path,
                'description': description,
                'href': self.env.href.build(config.name),
            }
            if not config.active:
                continue

            repos = self.env.get_repository(req.authname)
            if hasattr(repos, 'sync'):
                repos.sync()

            prev_rev = None
            for platform, rev, build in collect_changes(repos, config):
                if rev != prev_rev:
                    if prev_rev is None:
                        chgset = repos.get_changeset(rev)
                        req.hdf[prefix + '.youngest_rev'] = {
                            'id': rev, 'href': self.env.href.changeset(rev),
                            'author': chgset.author or 'anonymous',
                            'date': format_datetime(chgset.date),
                            'message': wiki_to_oneliner(
                                shorten_line(chgset.message), self.env)
                        }
                    else:
                        break
                    prev_rev = rev
                if build:
                    build_hdf = _build_to_hdf(self.env, req, build)
                    build_hdf['platform'] = platform.name
                    req.hdf[prefix + '.builds.%d' % platform.id] = build_hdf
                else:
                    req.hdf[prefix + '.builds.%d' % platform.id] = {
                        'platform': platform.name, 'status': 'pending'
                    }

        req.hdf['page.mode'] = 'overview'
        req.hdf['config.can_create'] = req.perm.has_permission('BUILD_CREATE')

    def _render_config(self, req, config_name):
        db = self.env.get_db_cnx()

        config = BuildConfig.fetch(self.env, config_name, db=db)
        req.hdf['title'] = 'Build Configuration "%s"' \
                           % config.label or config.name
        add_link(req, 'up', self.env.href.build(), 'Build Status')
        description = config.description
        if description:
            description = wiki_to_html(description, self.env, req)
        req.hdf['config'] = {
            'name': config.name, 'label': config.label, 'path': config.path,
            'min_rev': config.min_rev,
            'min_rev_href': self.env.href.changeset(config.min_rev),
            'max_rev': config.max_rev,
            'max_rev_href': self.env.href.changeset(config.max_rev),
            'active': config.active, 'description': description,
            'browser_href': self.env.href.browser(config.path),
            'can_modify': req.perm.has_permission('BUILD_MODIFY'),
            'can_delete': req.perm.has_permission('BUILD_DELETE')
        }
        req.hdf['page.mode'] = 'view_config'

        platforms = list(TargetPlatform.select(self.env, config=config_name,
                                               db=db))
        req.hdf['config.platforms'] = [
            {'name': platform.name, 'id': platform.id} for platform in platforms
        ]

        has_reports = False
        for report in Report.select(self.env, config=config.name, db=db):
            has_reports = True
            break

        if has_reports:
            req.hdf['config.charts'] = [
                {'href': self.env.href.build(config.name, 'chart/test')},
                {'href': self.env.href.build(config.name, 'chart/coverage')}
            ]
            charts_license = self.config.get('bitten', 'charts_license')
            if charts_license:
                req.hdf['config.charts_license'] = charts_license

        page = max(1, int(req.args.get('page', 1)))
        more = False
        req.hdf['page.number'] = page

        repos = self.env.get_repository(req.authname)
        if hasattr(repos, 'sync'):
            repos.sync()

        builds_per_page = 12 * len(platforms)
        idx = 0
        for platform, rev, build in collect_changes(repos, config):
            if idx >= page * builds_per_page:
                more = True
                break
            elif idx >= (page - 1) * builds_per_page:
                prefix = 'config.builds.%d' % rev
                req.hdf[prefix + '.href'] = self.env.href.changeset(rev)
                if build and build.status != Build.PENDING:
                    build_hdf = _build_to_hdf(self.env, req, build)
                    req.hdf['%s.%s' % (prefix, platform.id)] = build_hdf
                    for step in BuildStep.select(self.env, build=build.id,
                                                 db=db):
                        req.hdf['%s.%s.steps.%s' % (prefix, platform.id,
                                                    step.name)] = {
                            'description': step.description,
                            'duration': datetime.fromtimestamp(step.stopped) - \
                                        datetime.fromtimestamp(step.started),
                            'failed': not step.successful,
                            'errors': step.errors,
                            'href': build_hdf['href'] + '#step_' + step.name,
                        }
            idx += 1

        if page > 1:
            if page == 2:
                prev_href = self.env.href.build(config.name)
            else:
                prev_href = self.env.href.build(config.name, page=page - 1)
            add_link(req, 'prev', prev_href, 'Previous Page')
        if more:
            next_href = self.env.href.build(config.name, page=page + 1)
            add_link(req, 'next', next_href, 'Next Page')

    def _render_config_confirm(self, req, config_name):
        req.perm.assert_permission('BUILD_DELETE')
        config = BuildConfig.fetch(self.env, config_name)
        req.hdf['title'] = 'Delete Build Configuration "%s"' \
                           % config.label or config.name
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
                               % config.label or config.name
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
            req.hdf['title'] = 'Edit Target Platform "%s"' % platform.name
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

        formatters = []
        for formatter in self.log_formatters:
            formatters.append(formatter.get_formatter(req, build))

        summarizers = {} # keyed by report type
        for summarizer in self.report_summarizers:
            categories = summarizer.get_supported_categories()
            summarizers.update([(cat, summarizer) for cat in categories])

        req.hdf['build'] = _build_to_hdf(self.env, req, build)
        steps = []
        for step in BuildStep.select(self.env, build=build.id, db=db):
            steps.append({
                'name': step.name, 'description': step.description,
                'duration': pretty_timedelta(step.started, step.stopped),
                'failed': step.status == BuildStep.FAILURE,
                'errors': step.errors,
                'log': self._render_log(req, build, formatters, step),
                'reports': self._render_reports(req, config, build, summarizers,
                                                step)
            })
        req.hdf['build.steps'] = steps
        req.hdf['build.can_delete'] = req.perm.has_permission('BUILD_DELETE')

        repos = self.env.get_repository(req.authname)
        chgset = repos.get_changeset(build.rev)
        req.hdf['build.chgset_author'] = chgset.author

        add_stylesheet(req, 'bitten/bitten.css')
        return 'bitten_build.cs', None

    # ITimelineEventProvider methods

    def get_timeline_filters(self, req):
        if req.perm.has_permission('BUILD_VIEW'):
            yield ('build', 'Builds')

    def get_timeline_events(self, req, start, stop, filters):
        if 'build' not in filters:
            return

        add_stylesheet(req, 'bitten/bitten.css')

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("SELECT b.id,b.config,c.label,b.rev,p.name,"
                       "b.stopped,b.status FROM bitten_build AS b"
                       "  INNER JOIN bitten_config AS c ON (c.name=b.config) "
                       "  INNER JOIN bitten_platform AS p ON (p.id=b.platform) "
                       "WHERE b.stopped>=%s AND b.stopped<=%s "
                       "AND b.status IN (%s, %s) ORDER BY b.stopped",
                       (start, stop, Build.SUCCESS, Build.FAILURE))

        event_kinds = {Build.SUCCESS: 'successbuild',
                       Build.FAILURE: 'failedbuild'}
        for id, config, label, rev, platform, stopped, status in cursor:

            errors = []
            if status == Build.FAILURE:
                for step in BuildStep.select(self.env, build=id,
                                             status=BuildStep.FAILURE,
                                             db=db):
                    errors += [(step.name, error) for error
                               in step.errors]

            title = Markup('Build of <em>%s [%s]</em> on %s %s', label, rev,
                           platform, _status_label[status])
            message = ''
            if req.args.get('format') == 'rss':
                href = self.env.abs_href.build(config, id)
                if errors:
                    buf = StringIO()
                    prev_step = None
                    for step, error in errors:
                        if step != prev_step:
                            if prev_step is not None:
                                buf.write('</ul>')
                            buf.write('<p>Step %s failed:</p><ul>' \
                                      % escape(step))
                            prev_step = step
                        buf.write('<li>%s</li>' % escape(error))
                    buf.write('</ul>')
                    message = Markup(buf.getvalue())
            else:
                href = self.env.href.build(config, id)
                if errors:
                    steps = []
                    for step, error in errors:
                        if step not in steps:
                            steps.append(step)
                    steps = [Markup('<em>%s</em>', step) for step in steps]
                    if len(steps) < 2:
                        message = steps[0]
                    elif len(steps) == 2:
                        message = Markup(' and ').join(steps)
                    elif len(steps) > 2:
                        message = Markup(', ').join(steps[:-1]) + ', and ' + \
                                  steps[-1]
                    message = Markup('Step%s %s failed',
                                     len(steps) != 1 and 's' or '', message)
            yield event_kinds[status], href, title, stopped, None, message

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

    def _render_log(self, req, build, formatters, step):
        items = []
        for log in BuildLog.select(self.env, build=build.id, step=step.name):
            for level, message in log.messages:
                for format in formatters:
                    message = format(step, log.generator, level, message)
                items.append({'level': level, 'message': message})
        return items

    def _render_reports(self, req, config, build, summarizers, step):
        reports = []
        for report in Report.select(self.env, build=build.id, step=step.name):
            summarizer = summarizers.get(report.category)
            if summarizer:
                summary = summarizer.render_summary(req, config, build, step,
                                                    report.category)
            else:
                summary = None
            reports.append({'category': report.category,
                            'summary': Markup(summary)})
        return reports


class SourceFileLinkFormatter(Component):
    """Detects references to files in the build log and renders them as links
    to the repository browser."""

    implements(ILogFormatter)

    _fileref_re = re.compile('(?P<path>[\w.-]+(?:/[\w.-]+)+)(?P<line>(:\d+))')

    def get_formatter(self, req, build):
        """Return the log message formatter function."""
        config = BuildConfig.fetch(self.env, name=build.config)
        repos = self.env.get_repository(req.authname)
        href = self.env.href.browser
        cache = {}
        def _replace(m):
            filepath = posixpath.normpath(m.group('path').replace('\\', '/'))
            if not cache.get(filepath) is True:
                parts = filepath.split('/')
                path = ''
                for part in parts:
                    path = posixpath.join(path, part)
                    if not path in cache:
                        try:
                            repos.get_node(posixpath.join(config.path, path),
                                           build.rev)
                            cache[path] = True
                        except TracError:
                            cache[path] = False
                    if cache[path] is False:
                        return m.group(0)
            return '<a href="%s">%s</a>' % (
                   href(config.path, filepath) + '#L' + m.group('line')[1:],
                   m.group(0))
        def _formatter(step, type, level, message):
            return self._fileref_re.sub(_replace, message)
        return _formatter
