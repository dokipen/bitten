import re
from popen2 import Popen3

from bitten import BuildError

def distutils(basedir, command='build'):
    """Execute a `distutils` command."""
    cmdline = 'python setup.py %s' % command
    pipe = Popen3(cmdline, capturestderr=True) # FIXME: Windows compatibility
    while True:
        retval = pipe.poll()
        if retval != -1:
            break
        line = pipe.fromchild.readline()
        if line:
            print '[distutils] %s' % line.rstrip()
        line = pipe.childerr.readline()
        if line:
            print '[distutils] %s' % line.rstrip()
    if retval != 0:
        raise BuildError, "Executing distutils failed (%s)" % retval

def pylint(basedir, file=None):
    """Extract data from a `pylint` run written to a file."""
    assert file, 'Missing required attribute "file"'
    _msg_re = re.compile(r'^(?P<file>.+):(?P<line>\d+): '
                         r'\[(?P<type>[A-Z])(?:, (?P<tag>[\w\.]+))?\] '
                         r'(?P<msg>.*)$')
    for line in open(file, 'r'):
        match = _msg_re.search(line)
        if match:
            filename = match.group('file')
            if filename.startswith(basedir):
                filename = filename[len(basedir) + 1:]
            lineno = int(match.group('line'))

def trace(basedir, summary=None, coverdir=None, include=None, exclude=None):
    """Extract data from a `trac.py` run."""
    assert summary, 'Missing required attribute "summary"'
    assert coverdir, 'Missing required attribute "coverdir"'

def unittest(basedir, file=None):
    """Extract data from a unittest results file in XML format."""
    assert file, 'Missing required attribute "file"'
