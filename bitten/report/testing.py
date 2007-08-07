# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

from trac.core import *
from trac.web.chrome import Chrome
from trac.web.clearsilver import HDFWrapper
from bitten.api import IReportChartGenerator, IReportSummarizer


class TestResultsChartGenerator(Component):
    implements(IReportChartGenerator)

    # IReportChartGenerator methods

    def get_supported_categories(self):
        return ['test']

    def generate_chart_data(self, req, config, category):
        assert category == 'test'

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
SELECT build.rev, build.platform, item_status.value AS status, COUNT(*) AS num
FROM bitten_build AS build
 LEFT OUTER JOIN bitten_report AS report ON (report.build=build.id)
 LEFT OUTER JOIN bitten_report_item AS item_status
  ON (item_status.report=report.id AND item_status.name='status')
WHERE build.config=%s AND report.category='test'
GROUP BY build.rev_time, build.rev, build.platform, item_status.value
ORDER BY build.rev_time, build.platform""", (config.name,))

        prev_rev = None
        prev_platform, platform_total = None, 0
        tests = []
        for rev, platform, status, num in cursor:
            if rev != prev_rev:
                tests.append([rev, 0, 0])
                prev_rev = rev
                platform_total = 0
            if platform != prev_platform:
                prev_platform = platform
                platform_total = 0

            platform_total += num
            tests[-1][1] = max(platform_total, tests[-1][1])
            if status != 'success':
                tests[-1][2] = max(num, tests[-1][2])

        req.hdf['chart.title'] = 'Unit Tests'
        req.hdf['chart.data'] = [
            [''] + ['[%s]' % item[0] for item in tests],
            ['Total'] + [item[1] for item in tests],
            ['Failures'] + [item[2] for item in tests]
        ]

        return 'bitten_chart_tests.cs'


class TestResultsSummarizer(Component):
    implements(IReportSummarizer)

    # IReportSummarizer methods

    def get_supported_categories(self):
        return ['test']

    def render_summary(self, req, config, build, step, category):
        assert category == 'test'

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
SELECT item_fixture.value AS fixture, item_file.value AS file,
       COUNT(item_success.value) AS num_success,
       COUNT(item_failure.value) AS num_failure,
       COUNT(item_error.value) AS num_error
FROM bitten_report AS report
 LEFT OUTER JOIN bitten_report_item AS item_fixture
  ON (item_fixture.report=report.id AND item_fixture.name='fixture')
 LEFT OUTER JOIN bitten_report_item AS item_file
  ON (item_file.report=report.id AND item_file.item=item_fixture.item AND
      item_file.name='file')
 LEFT OUTER JOIN bitten_report_item AS item_success
  ON (item_success.report=report.id AND item_success.item=item_fixture.item AND
      item_success.name='status' AND item_success.value='success')
 LEFT OUTER JOIN bitten_report_item AS item_failure
  ON (item_failure.report=report.id AND item_failure.item=item_fixture.item AND
      item_failure.name='status' AND item_failure.value='failure')
 LEFT OUTER JOIN bitten_report_item AS item_error
  ON (item_error.report=report.id AND item_error.item=item_fixture.item AND
      item_error.name='status' AND item_error.value='error')
WHERE category='test' AND build=%s AND step=%s
GROUP BY file, fixture
ORDER BY fixture""", (build.id, step.name))

        data = []
        total_success, total_failure, total_error = 0, 0, 0
        for fixture, file, num_success, num_failure, num_error in cursor:
            data.append({'name': fixture, 'num_success': num_success,
                         'num_error': num_error, 'num_failure': num_failure})
            total_success += num_success
            total_failure += num_failure
            total_error += num_error
            if file:
                data[-1]['href'] = req.href.browser(config.path, file)

        hdf = HDFWrapper(loadpaths=Chrome(self.env).get_all_templates_dirs())
        hdf['data'] = data
        hdf['totals'] = {'success': total_success, 'failure': total_failure,
                         'error': total_error}
        return hdf.render('bitten_summary_tests.cs')
