import os
import re

from elementtree import ElementTree
from trac.core import *
from bitten import BuildError
from bitten.recipe import IReportProcessor


class TraceReportProcessor(Component):
    implements(IReportProcessor)

    def get_name(self):
        return 'trace'

    def process(self, basedir, summary=None, coverdir=None, include=None,
                exclude=None):
        assert summary, 'Missing required attribute "summary"'
        assert coverdir, 'Missing required attribute "coverdir"'
