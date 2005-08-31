# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

from datetime import datetime
import re

from trac.core import *
from trac.web import IRequestHandler
from bitten.model import BuildConfig, Build
from bitten.store import ReportStore
from bitten.util import xmlio


class BittenChartRenderer(Component):
    implements(IRequestHandler)

    # IRequestHandler methods

    def match_request(self, req):
        match = re.match(r'/build/([\w.-]+)/chart/(\w+)', req.path_info)
        if match:
            req.args['config'] = match.group(1)
            req.args['type'] = match.group(2)
            return True

    def process_request(self, req):
        type = req.args.get('type')
        config = BuildConfig.fetch(self.env, name=req.args.get('config'))
        if type == 'unittest':
            return self._render_tests(req, config)
        elif type == 'trace':
            return self._render_coverage(req, config)
        else:
            raise TracError, 'Unknown report type'

    # Internal methods

    def _render_tests(self, req, config):
        rev_time = {}
        rev = {}
        for build in Build.select(self.env, config=config.name):
            rev[str(build.id)] = build.rev
            rev_time[str(build.id)] = build.rev_time

        store = ReportStore(self.env)
        query = """
for $report in $reports
return
    <tests build="{dbxml:metadata('build', $report)}"
           total="{count($report/test)}"
           failed="{count($report/test[@status='error' or @status='failure'])}">
    </tests>
"""

        tests = []
        for test in store.query_reports(query, config=config, type='unittest'):
            tests.append({
                'time': datetime.fromtimestamp(rev_time[test.attr['build']]),
                'rev': rev[test.attr['build']], 'total': test.attr['total'],
                'failed': test.attr['failed'],
            })
        tests.sort(lambda x, y: cmp(x['time'], y['time']))

        req.hdf['chart.title'] = 'Unit Tests'
        req.hdf['chart.data'] = tests

        return 'bitten_chart_tests.cs', 'text/xml'

    def _render_coverage(self, req, config):
        rev_time = {}
        rev = {}
        for build in Build.select(self.env, config=config.name):
            rev[str(build.id)] = build.rev
            rev_time[str(build.id)] = build.rev_time

        store = ReportStore(self.env)
        query = """
for $report in $reports
return
    <coverage build="{dbxml:metadata('build', $report)}"
              loc="{count($report/coverage/line)}">
    {
        for $coverage in $report/coverage
        return
            count($coverage/line) * ($coverage/@percentage/text() div 100)
    }
    </coverage>
"""

        coverage = []
        for test in store.query_reports(query, config=config, type='trace'):
            values = [float(val) for val in test.gettext().split()]
            coverage.append({
                'time': datetime.fromtimestamp(rev_time[test.attr['build']]),
                'rev': rev[test.attr['build']], 'loc': test.attr['loc'],
                'cov': int(sum(values))
            })
        coverage.sort(lambda x, y: cmp(x['time'], y['time']))


        req.hdf['chart.title'] = 'Code Coverage'
        req.hdf['chart.data'] = coverage

        return 'bitten_chart_coverage.cs', 'text/xml'
