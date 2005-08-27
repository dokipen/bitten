# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

from trac.core import *
from trac.web.clearsilver import HDFWrapper
from bitten.model import BuildConfig
from bitten.trac_ext.api import IReportSummarizer

__all__ = ['TestResultsSummarizer']


class TestResultsSummarizer(Component):
    implements(IReportSummarizer)

    template = """<h3>Test Results</h3>
<table class="listing tests">
 <thead><tr>
  <th>Test Fixture</th><th>Total</th>
  <th>Failures</th><th>Errors</th>
 </tr></thead>
 <tbody><?cs
 each:fixture = fixtures ?><tr><td><a href="<?cs
  var:fixture.href ?>"><?cs var:fixture.name ?></a></td><td><?cs
  var:fixture.total ?></td><td><?cs var:fixture.failures ?></td><td><?cs
  var:fixture.errors ?></td></tr><?cs
 /each ?></tbody>
</table>
"""

    def get_supported_report_types(self):
        return ['unittest']

    def render_report_summary(self, req, build, step, report):
        config = BuildConfig.fetch(self.env, name=build.config)
        fixtures = {}
        for test in report.children('test'):
            filename = test.attr.get('file')
            name = test.attr.get('fixture') or filename
            status = test.attr.get('status')
            if name in fixtures:
                fixtures[name]['total'] += 1
                fixtures[name]['errors'] += int(status == 'error')
                fixtures[name]['failures'] += int(status == 'failure')
            else:
                file_href = None
                if filename:
                    file_href = self.env.href.browser(config.path, filename,
                                                      rev=build.rev)
                fixtures[name] = {'name': name, 'href': file_href, 'total': 1,
                                  'errors': int(status == 'error'),
                                  'failures': int(status == 'failure')}
        hdf = HDFWrapper()
        names = fixtures.keys()
        names.sort()
        for idx, name in enumerate(names):
            hdf['fixtures.%d' % idx] = fixtures[name]
        return hdf.parse(self.template).render()


class CodeCoverageSummarizer(Component):
    implements(IReportSummarizer)

    template = """<h3>Code Coverage</h3>
<table class="listing coverage">
 <thead><tr><th>Unit</th><th>Percent</th></tr></thead>
 <tbody><?cs
 each:unit = units ?><tr><td><a href="<?cs
  var:unit.href ?>"><?cs var:unit.name ?></a></td><td><?cs
  var:unit.percentage ?></td></tr><?cs
 /each ?></tbody>
</table>
"""

    def get_supported_report_types(self):
        return ['trace']

    def render_report_summary(self, req, build, step, report):
        config = BuildConfig.fetch(self.env, name=build.config)
        units = {}
        for coverage in report.children('coverage'):
            filename = coverage.attr.get('file')
            if filename:
                file_href = self.env.href.browser(config.path, filename,
                                                  rev=build.rev)
            name = coverage.attr.get('module')
            units[name] = {'name': name, 'href': file_href,
                           'percentage': coverage.attr['percentage']}

        hdf = HDFWrapper()
        names = units.keys()
        names.sort()
        for idx, name in enumerate(names):
            hdf['units.%d' % idx] = units[name]
        return hdf.parse(self.template).render()
