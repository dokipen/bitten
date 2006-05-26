# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

from trac.core import *
from trac.web.chrome import Chrome
from trac.web.clearsilver import HDFWrapper
from bitten.trac_ext.api import IReportSummarizer


class TestResultsSummarizer(Component):
    implements(IReportSummarizer)

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
GROUP BY file, fixture ORDER BY fixture""", (build.id, step.name))

        data = []
        total_success, total_failure, total_error = 0, 0, 0
        for fixture, file, num_success, num_failure, num_error in cursor:
            data.append({'name': fixture, 'num_success': num_success,
                         'num_error': num_error, 'num_failure': num_failure})
            total_success += num_success
            total_failure += num_failure
            total_error += num_error
            if file:
                data[-1]['href'] = self.env.href.browser(config.path, file)

        hdf = HDFWrapper(loadpaths=Chrome(self.env).get_all_templates_dirs())
        hdf['data'] = data
        hdf['totals'] = {'success': total_success, 'failure': total_failure,
                         'error': total_error}
        return hdf.render('bitten_summary_tests.cs')


class TestCoverageSummarizer(Component):
    implements(IReportSummarizer)

    def get_supported_categories(self):
        return ['coverage']

    def render_summary(self, req, config, build, step, category):
        assert category == 'coverage'

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
SELECT item_name.value AS unit, item_file.value AS file,
       item_lines.value AS loc, item_percentage.value AS cov
FROM bitten_report AS report
 LEFT OUTER JOIN bitten_report_item AS item_name
  ON (item_name.report=report.id AND item_name.name='name')
 LEFT OUTER JOIN bitten_report_item AS item_file
  ON (item_file.report=report.id AND item_file.item=item_name.item AND
      item_file.name='file')
 LEFT OUTER JOIN bitten_report_item AS item_lines
  ON (item_lines.report=report.id AND item_lines.item=item_name.item AND
      item_lines.name='lines')
 LEFT OUTER JOIN bitten_report_item AS item_percentage
  ON (item_percentage.report=report.id AND
      item_percentage.item=item_name.item AND
      item_percentage.name='percentage')
WHERE category='coverage' AND build=%s AND step=%s
GROUP BY file, unit ORDER BY unit""", (build.id, step.name))

        data = []
        total_loc, total_cov = 0, 0
        for unit, file, loc, cov in cursor:
            loc, cov = int(loc), float(cov)
            if loc:
                d = {'name': unit, 'loc': loc, 'cov': int(cov)}
                if file:
                    d['href'] = self.env.href.browser(config.path, file)
                data.append(d)
                total_loc += loc
                total_cov += loc * cov

        hdf = HDFWrapper(loadpaths=Chrome(self.env).get_all_templates_dirs())
        hdf['data'] = data
        hdf['totals'] = {'loc': total_loc, 'cov': int(total_cov / total_loc)}
        return hdf.render('bitten_summary_coverage.cs')
