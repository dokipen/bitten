import os
import re

from elementtree import ElementTree
from trac.core import *
from bitten import BuildError
from bitten.recipe import IReportProcessor


_test_re = re.compile(r'^(?P<testname>\w+) \((?P<testcase>\d+): '
                      r'\[(?P<type>[A-Z])(?:, (?P<tag>[\w\.]+))?\] '
                      r'(?P<msg>.*)$')

class UnittestReportProcessor(Component):
    implements(IReportProcessor)

    def get_name(self):
        return 'unittest'

    def process(self, basedir, file=None):
        assert file, 'Missing required attribute "file"'
