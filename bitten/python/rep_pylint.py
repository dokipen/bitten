import os
import re

from elementtree import ElementTree
from trac.core import *
from bitten import BuildError
from bitten.recipe import IReportProcessor


_msg_re = re.compile(r'^(?P<file>.+):(?P<line>\d+): '
                     r'\[(?P<type>[A-Z])(?:, (?P<tag>[\w\.]+))?\] '
                     r'(?P<msg>.*)$')

class PylintReportProcessor(Component):
    implements(IReportProcessor)

    def get_name(self):
        return 'pylint'

    def process(self, basedir, file=None):
        assert file, 'Missing required attribute "file"'

        for line in open(file, 'r'):
            match = _msg_re.search(line)
            if match:
                filename = match.group('file')
                if filename.startswith(basedir):
                    filename = filename[len(basedir) + 1:]
                lineno = int(match.group('line'))
