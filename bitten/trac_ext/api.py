# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

from trac.core import *


class ILogFormatter(Interface):
    """Extension point interface for components that format build log
    messages."""

    def get_formatter(req, build, step, type):
        """Return a function that gets called for every log message.
        
        The function must take two positional arguments, `level` and `message`,
        and return the formatted message.
        """


class IReportSummarizer(Interface):
    """Extension point interface for components that render a summary of reports
    of some kind."""

    def get_supported_report_types():
        """Return a list of strings identifying the types of reports this 
        component supports."""

    def render_report_summary(req, build, step, report):
        """Render a summary for the given report and return the results HTML as
        a string."""
