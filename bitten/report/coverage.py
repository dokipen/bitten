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
from bitten.trac_ext.api import IReportChartGenerator, IReportSummarizer


class TestCoverageChartGenerator(Component):
    implements(IReportChartGenerator)

    # IReportChartGenerator methods

    def get_supported_categories(self):
        return ['coverage']

    def generate_chart_data(self, req, config, category):
        assert category == 'coverage'

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
SELECT build.rev, SUM(%s) AS loc, SUM(%s * %s / 100) AS cov
FROM bitten_build AS build
 LEFT OUTER JOIN bitten_report AS report ON (report.build=build.id)
 LEFT OUTER JOIN bitten_report_item AS item_lines
  ON (item_lines.report=report.id AND item_lines.name='lines')
 LEFT OUTER JOIN bitten_report_item AS item_percentage
  ON (item_percentage.report=report.id AND item_percentage.name='percentage' AND
      item_percentage.item=item_lines.item)
WHERE build.config=%%s AND report.category='coverage'
GROUP BY build.rev_time, build.rev, build.platform
ORDER BY build.rev_time""" % (db.cast('item_lines.value', 'int'),
                              db.cast('item_lines.value', 'int'),
                              db.cast('item_percentage.value', 'int')),
                              (config.name,))

        prev_rev = None
        coverage = []
        for rev, loc, cov in cursor:
            if rev != prev_rev:
                coverage.append([rev, 0, 0])
            if loc > coverage[-1][1]:
                coverage[-1][1] = int(loc)
            if cov > coverage[-1][2]:
                coverage[-1][2] = int(cov)
            prev_rev = rev

        req.hdf['chart.title'] = 'Test Coverage'
        req.hdf['chart.data'] = [
            [''] + ['[%s]' % item[0] for item in coverage],
            ['Lines of code'] + [item[1] for item in coverage],
            ['Coverage'] + [int(item[2]) for item in coverage]
        ]

        return 'bitten_chart_coverage.cs'


class TestCoverageSummarizer(Component):
    implements(IReportSummarizer)

    # IReportSummarizer methods

    def get_supported_categories(self):
        return ['coverage']

    def render_summary(self, req, config, build, step, category):
        assert category == 'coverage'

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        cursor.execute("""
SELECT item_name.value AS unit, item_file.value AS file,
       max(item_lines.value) AS loc, max(item_percentage.value) AS cov
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
GROUP BY file, item_name.value
ORDER BY item_name.value""", (build.id, step.name))

        data = []
        total_loc, total_cov = 0, 0
        for unit, file, loc, cov in cursor:
            try:
                loc, cov = int(loc), float(cov)
            except TypeError:
                continue # no rows
            if loc:
                d = {'name': unit, 'loc': loc, 'cov': int(cov)}
                if file:
                    d['href'] = req.href.browser(config.path, file)
                data.append(d)
                total_loc += loc
                total_cov += loc * cov

        coverage = 0
        if total_loc != 0:
            coverage = total_cov // total_loc

        hdf = HDFWrapper(loadpaths=Chrome(self.env).get_all_templates_dirs())
        hdf['data'] = data
        hdf['totals'] = {'loc': total_loc, 'cov': int(coverage)}
        return hdf.render('bitten_summary_coverage.cs')
