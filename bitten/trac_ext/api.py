# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

from trac.core import *


class IBuildListener(Interface):
    """Extension point interface for components that need to be notified of
    build events.
    
    Note that these will be notified in the process running the build master."""

    def build_started(build):
        """Called when a build slave has accepted a build initiation.
        
        @param build: The `bitten.model.Build` instance representing the build
        """

    def build_aborted(config, build):
        """Called when a build slave cancels a build or disconnects.
        
        @param build: The `bitten.model.Build` instance representing the build
        """

    def build_completed(config, build):
        """Called when a build slave has completed a build, regardless of the
        outcome.
        
        @param build: The `bitten.model.Build` instance representing the build
        """


class ILogFormatter(Interface):
    """Extension point interface for components that format build log
    messages."""

    def get_formatter(req, build):
        """Return a function that gets called for every log message.
        
        The function must take four positional arguments, `step`, `generator`,
        `level` and `message`, and return the formatted message.
        """


class IReportSummarizer(Interface):
    """Extension point interface for components that render a summary of reports
    of some kind."""

    def get_supported_categories():
        """Return a list of strings identifying the types of reports this 
        component supports."""

    def render_summary(req, config, build, step, category):
        """Render a summary for the given report and return the results HTML as
        a string."""


class IReportChartGenerator(Interface):
    """Extension point interface for components that generator a chart for a
    set of reports."""

    def get_supported_categories():
        """Return a list of strings identifying the types of reports this 
        component supports."""

    def generate_chart_data(req, config, category):
        """Generate the data for the chart.
        
        This method should store the data in the HDF of the request and return
        the name of the template that should process the data."""
