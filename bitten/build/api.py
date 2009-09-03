# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

"""Functions and classes used to simplify the implementation recipe commands."""

import logging
import fnmatch
import os
import shlex
import time
import subprocess
import sys


log = logging.getLogger('bitten.build.api')

__docformat__ = 'restructuredtext en'


class BuildError(Exception):
    """Exception raised when a build fails."""


class TimeoutError(Exception):
    """Exception raised when the execution of a command times out."""


def _encode(text):
    """Encode input for call. Input must be unicode or utf-8 string."""
    if not isinstance(text, unicode):
        text = unicode(text, 'utf-8')
    return text.encode(
                sys.getfilesystemencoding() or sys.stdin.encoding, 'replace')

def _decode(text):
    """Decode output from call."""
    try:
        return text.decode('utf-8')
    except UnicodeDecodeError:
        return text.decode(sys.stdout.encoding, 'replace')


class CommandLine(object):
    """Simple helper for executing subprocesses."""

    def __init__(self, executable, args, input=None, cwd=None):
        """Initialize the CommandLine object.
        
        :param executable: the name of the program to execute
        :param args: a list of arguments to pass to the executable
        :param input: string or file-like object containing any input data for
                      the program
        :param cwd: the working directory to change to before executing the
                    command
        """
        self.executable = executable
        self.arguments = [_encode(arg) for arg in args]
        self.input = input
        self.cwd = cwd
        if self.cwd:
            assert os.path.isdir(self.cwd)
        self.returncode = None


    def execute(self, timeout=None):
        """Execute the command, and return a generator for iterating over
        the output written to the standard output and error streams.
        
        :param timeout: number of seconds before the external process
                        should be aborted (not supported on Windows without
                        ``subprocess`` module / Python 2.4+)
        """
        from threading import Thread
        from Queue import Queue, Empty

        def reader(pipe, pipe_name, queue):
            while pipe and not pipe.closed:
                line = pipe.readline()
                if line == '':
                    break
                queue.put((pipe_name, line))
            if not pipe.closed:
                pipe.close()

        def writer(pipe, data):
            if data and pipe and not pipe.closed:
                pipe.write(data)
            if not pipe.closed:
                pipe.close()

        args = [self.executable] + self.arguments
        try:
            p = subprocess.Popen(args, bufsize=1, # Line buffered
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=(self.cwd or None),
                        shell=(os.name == 'nt' and True or False),
                        universal_newlines=True,
                        env=None)
        except Exception, e:
            # NT executes through shell and will not raise BuildError
            raise BuildError('Error executing %s: %s %s' % (args,
                                        e.__class__.__name__, str(e)))

        log.debug('Executing %s, (pid = %s)', args, p.pid)

        if self.input:
            if isinstance(self.input, basestring):
                in_data = self.input
            else:
                in_data = self.input.read()
        else:
            in_data = None
        
        queue = Queue()
        limit = timeout and timeout + time.time() or 0

        pipe_in = Thread(target=writer, args=(p.stdin, in_data))
        pipe_out = Thread(target=reader, args=(p.stdout, 'stdout', queue))
        pipe_err = Thread(target=reader, args=(p.stderr, 'stderr', queue))
        pipe_err.start(); pipe_out.start(); pipe_in.start()

        while True:
            if limit and limit < time.time():
                if hasattr(subprocess, 'kill'): # Python 2.6+
                    p.kill()
                raise TimeoutError('Command %s timed out' % self.executable)
            if p.poll() != None and self.returncode == None:
                self.returncode = p.returncode
            try:
                name, line = queue.get(block=True, timeout=.01)
                line = line and _decode(line.rstrip().replace('\x00', ''))
                if name == 'stderr':
                    yield (None, line)
                else:
                    yield (line, None)
            except Empty:
                if self.returncode != None:
                    break

        pipe_out.join(); pipe_in.join(); pipe_err.join()

        log.debug('%s exited with code %s', self.executable,
                  self.returncode)


class FileSet(object):
    """Utility class for collecting a list of files in a directory that match
    given name/path patterns."""

    DEFAULT_EXCLUDES = ['CVS/*', '*/CVS/*', '.svn/*', '*/.svn/*',
                        '.DS_Store', 'Thumbs.db']

    def __init__(self, basedir, include=None, exclude=None):
        """Create a file set.
        
        :param basedir: the base directory for all files in the set
        :param include: a list of patterns that define which files should be
                        included in the set
        :param exclude: a list of patterns that define which files should be
                        excluded from the set
        """
        self.files = []
        self.basedir = basedir

        self.include = []
        if include is not None:
            self.include = shlex.split(include)

        self.exclude = self.DEFAULT_EXCLUDES[:]
        if exclude is not None:
            self.exclude += shlex.split(exclude)

        for dirpath, dirnames, filenames in os.walk(self.basedir):
            dirpath = dirpath[len(self.basedir) + 1:]

            for filename in filenames:
                filepath = nfilepath = os.path.join(dirpath, filename)
                if os.sep != '/':
                    nfilepath = nfilepath.replace(os.sep, '/')

                if self.include:
                    included = False
                    for pattern in self.include:
                        if fnmatch.fnmatchcase(nfilepath, pattern) or \
                           fnmatch.fnmatchcase(filename, pattern):
                            included = True
                            break
                    if not included:
                        continue

                excluded = False
                for pattern in self.exclude:
                    if fnmatch.fnmatchcase(nfilepath, pattern) or \
                       fnmatch.fnmatchcase(filename, pattern):
                        excluded = True
                        break
                if not excluded:
                    self.files.append(filepath)

    def __iter__(self):
        """Iterate over the names of all files in the set."""
        for filename in self.files:
            yield filename

    def __contains__(self, filename):
        """Return whether the given file name is in the set.
        
        :param filename: the name of the file to check
        """
        return filename in self.files
