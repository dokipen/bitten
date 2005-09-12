# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

from trac.core import *
from trac.util import escape
from trac.web.chrome import Chrome
from trac.web.clearsilver import HDFWrapper
from bitten.model import BuildConfig
from bitten.store import get_store
from bitten.trac_ext.api import IReportSummarizer


class XQuerySummarizer(Component):
    abstract = True
    implements(IReportSummarizer)

    query = None
    report_type = None
    template = None

    def get_supported_report_types(self):
        return [self.report_type]

    def render_report_summary(self, req, build, step, report):
        hdf = HDFWrapper(loadpaths=Chrome(self.env).get_all_templates_dirs())
        config = BuildConfig.fetch(self.env, name=build.config)
        store = get_store(self.env)
        results = store.query(self.query, config=config, build=build, step=step,
                              type=self.report_type)
        for idx, elem in enumerate(results):
            data = {}
            for name, value in elem.attr.items():
                if name == 'file':
                    data['href'] = escape(self.env.href.browser(config.path,
                                                                value,
                                                                rev=build.rev))
                data[name] = escape(value)
            hdf['data.%d' % idx] = data

        return hdf.render(self.template)


class TestResultsSummarizer(XQuerySummarizer):

    report_type = 'unittest'
    template = 'bitten_summary_tests.cs'

    query = """
for $report in $reports
return
    for $fixture in distinct-values($report/test/@fixture)
    order by $fixture
    return
        let $tests := $report/test[@fixture=$fixture]
        return
            <test name="{$fixture}" file="{$tests[1]/@file}"
                  success="{count($tests[@status='success'])}"
                  errors="{count($tests[@status='error'])}"
                  failures="{count($tests[@status='failure'])}"/>
"""



class CodeCoverageSummarizer(XQuerySummarizer):

    report_type = 'trace'
    template = 'bitten_summary_coverage.cs'

    query = """
for $report in $reports
where $report/@type = 'trace'
return
    for $coverage in $report/coverage
    order by $coverage/@file
    return
        <unit file="{$coverage/@file}" name="{$coverage/@module}"
              loc="{count($coverage/line)}" cov="{$coverage/@percentage}%"/>
"""
