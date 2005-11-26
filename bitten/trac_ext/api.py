# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

"""Interfaces of extension points provided by the Bitten Trac plugin."""

from trac.core import *


class IBuildListener(Interface):
    """Extension point interface for components that need to be notified of
    build events.
    
    Note that these will be notified in the process running the build master,
    not the web interface.
    """

    def build_started(build):
        """Called when a build slave has accepted a build initiation.
        
        @param build: the build that was started
        @type build: an instance of L{bitten.model.Build}
        """

    def build_aborted(build):
        """Called when a build slave cancels a build or disconnects.
        
        @param build: the build that was aborted
        @type build: an instance of L{bitten.model.Build}
        """

    def build_completed(build):
        """Called when a build slave has completed a build, regardless of the
        outcome.
        
        @param build: the build that was aborted
        @type build: an instance of L{bitten.model.Build}
        """


class ILogFormatter(Interface):
    """Extension point interface for components that format build log
    messages."""

    def get_formatter(req, build):
        """Return a function that gets called for every log message.
        
        The function must take four positional arguments, C{step},
        C{generator}, C{level} and C{message}, and return the formatted
        message as a string.

        @param req: the request object
        @param build: the build to which the logs belong that should be
            formatted
        @type build: an instance of L{bitten.model.Build}
        """


class IReportSummarizer(Interface):
    """Extension point interface for components that render a summary of reports
    of some kind."""

    def get_supported_categories():
        """Return a list of strings identifying the types of reports this 
        component supports."""

    def render_summary(req, config, build, step, category):
        """Render a summary for the given report and return the results HTML as
        a string.
        
        @param req: the request object
        @param config: the build configuration
        @type config: an instance of L{bitten.model.BuildConfig}
        @param build: the build
        @type build: an instance of L{bitten.model.Build}
        @param step: the build step
        @type step: an instance of L{bitten.model.BuildStep}
        @param category: the category of the report that should be summarized
        """


class IReportChartGenerator(Interface):
    """Extension point interface for components that generator a chart for a
    set of reports."""

    def get_supported_categories():
        """Return a list of strings identifying the types of reports this 
        component supports."""

    def generate_chart_data(req, config, category):
        """Generate the data for a report chart.
        
        This method should store the data in the HDF of the request and return
        the name of the template that should process the data.
        
        @param req: the request object
        @param config: the build configuration
        @type config: an instance of L{bitten.model.BuildConfig}
        @param category: the category of reports to include in the chart
        """
