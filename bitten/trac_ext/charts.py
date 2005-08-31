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
from bitten.trac_ext.api import IReportChartGenerator
from bitten.util import xmlio


class BittenChartRenderer(Component):
    implements(IRequestHandler)

    generators = ExtensionPoint(IReportChartGenerator)

    # IRequestHandler methods

    def match_request(self, req):
        match = re.match(r'/build/([\w.-]+)/chart/(\w+)', req.path_info)
        if match:
            req.args['config'] = match.group(1)
            req.args['type'] = match.group(2)
            return True

    def process_request(self, req):
        report_type = req.args.get('type')
        config = BuildConfig.fetch(self.env, name=req.args.get('config'))

        for generator in self.generators:
            if report_type in generator.get_supported_report_types():
                template = generator.generate_chart_data(req, config,
                                                         report_type)
                break
        else:
            raise TracError, 'Unknown report type "%s"' % report_type

        return template, 'text/xml'


class TestResultsChartGenerator(Component):
    implements(IReportChartGenerator)

    # IReportChartGenerator methods

    def get_supported_report_types(self):
        return ['unittest']

    def generate_chart_data(self, req, config, report_type):
        rev_map = {}
        for build in Build.select(self.env, config=config.name):
            if build.status in (Build.PENDING, Build.IN_PROGRESS):
                continue
            rev_map[str(build.id)] = (build.rev,
                                      datetime.fromtimestamp(build.rev_time))

        store = ReportStore(self.env)
        xquery = """
for $report in $reports
return
    <tests build="{dbxml:metadata('build', $report)}"
           total="{count($report/test)}"
           failed="{count($report/test[@status='error' or @status='failure'])}">
    </tests>
"""

        # FIXME: It should be possible to aggregate the test counts by revision
        #        in the XQuery above, somehow. For now, we do that in the Python
        #        code

        tests = {} # Accumulated test numbers by revision
        for test in store.query_reports(xquery, config=config, type='unittest'):
            rev, rev_time = rev_map.get(test.attr['build'])
            if rev not in tests:
                tests[rev] = [rev_time, 0, 0]
            tests[rev][1] = max(int(test.attr['total']), tests[rev][1])
            tests[rev][2] = max(int(test.attr['failed']), tests[rev][2])

        tests = [(rev_time, rev, total, failed) for
                 rev, (rev_time, total, failed) in tests.items()]
        tests.sort()

        req.hdf['chart.title'] = 'Unit Tests'
        req.hdf['chart.data'] = [
            [''] + [item[1] for item in tests],
            ['Total'] + [item[2] for item in tests],
            ['Failures'] + [int(item[3]) for item in tests]
        ]

        return 'bitten_chart_tests.cs'


class TestResultsChartGenerator(Component):
    implements(IReportChartGenerator)

    # IReportChartGenerator methods

    def get_supported_report_types(self):
        return ['trace']

    def generate_chart_data(self, req, config, report_type):
        rev_map = {}
        for build in Build.select(self.env, config=config.name):
            if build.status in (Build.PENDING, Build.IN_PROGRESS):
                continue
            rev_map[str(build.id)] = (build.rev,
                                      datetime.fromtimestamp(build.rev_time))

        store = ReportStore(self.env)
        xquery = """
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

        # FIXME: It should be possible to aggregate the coverage info by
        #        revision in the XQuery above, somehow. For now, we do that in
        #        the Python code

        coverage = {} # Accumulated coverage info by revision
        for test in store.query_reports(xquery, config=config, type='trace'):
            rev, rev_time = rev_map.get(test.attr['build'])
            if rev not in coverage:
                coverage[rev] = [rev_time, 0, 0]
            coverage[rev][1] = max(int(test.attr['loc']), coverage[rev][1])
            cov_lines = sum([float(val) for val in test.gettext().split()])
            coverage[rev][2] = max(cov_lines, coverage[rev][2])

        coverage = [(rev_time, rev, loc, cov) for
                    rev, (rev_time, loc, cov) in coverage.items()]
        coverage.sort()

        req.hdf['chart.title'] = 'Code Coverage'
        req.hdf['chart.data'] = [
            [''] + [item[1] for item in coverage],
            ['Lines of code'] + [item[2] for item in coverage],
            ['Coverage'] + [int(item[3]) for item in coverage]
        ]

        return 'bitten_chart_coverage.cs'
