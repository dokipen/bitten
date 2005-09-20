# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import logging
import fnmatch
import os
import shlex

log = logging.getLogger('bitten.build.api')


class BuildError(Exception):
    """Exception raised when a build fails."""


class TimeoutError(Exception):
    """Exception raised when the execution of a command times out."""


class CommandLine(object):
    """Simple helper for executing subprocesses."""
    # TODO: Use 'subprocess' module if available (Python >= 2.4)

    def __init__(self, executable, args, input=None, cwd=None):
        """Initialize the CommandLine object.
        
        @param executable The name of the program to execute
        @param args A list of arguments to pass to the executable
        @param input String or file-like object containing any input data for
                     the program
        @param cwd The working directory to change to before executing the
                   command
        """
        self.executable = executable
        self.arguments = [str(arg) for arg in args]
        self.input = input
        self.cwd = cwd
        if self.cwd:
            assert os.path.isdir(self.cwd)
        self.returncode = None

    if os.name == 'nt': # windows

        def execute(self, timeout=None):
            args = [self.executable] + self.arguments
            for idx, arg in enumerate(args):
                if arg.find(' ') >= 0:
                    args[idx] = '"%s"' % arg
            log.debug('Executing %s', args)

            if self.cwd:
                old_cwd = os.getcwd()
                os.chdir(self.cwd)

            import tempfile
            in_name = None
            if self.input:
                if isinstance(self.input, basestring):
                    in_file, in_name = tempfile.mkstemp(prefix='bitten_',
                                                        suffix='.pipe')
                    os.write(in_file, self.input)
                    os.close(in_file)
                    in_redirect = '< "%s" ' % in_name
                else:
                    in_redirect = '< "%s" ' % self.input.name
            else:
                in_redirect = ''

            out_file, out_name = tempfile.mkstemp(prefix='bitten_',
                                                  suffix='.pipe')
            os.close(out_file)
            err_file, err_name = tempfile.mkstemp(prefix='bitten_',
                                                  suffix='.pipe')
            os.close(err_file)

            try:
                cmd = '( %s ) > "%s" %s 2> "%s"' % (' '.join(args), out_name,
                                                    in_redirect, err_name)
                self.returncode = os.system(cmd)
                log.debug('Exited with code %s', self.returncode)

                out_file = file(out_name, 'r')
                err_file = file(err_name, 'r')
                out_lines = out_file.readlines()
                err_lines = err_file.readlines()
                out_file.close()
                err_file.close()
            finally:
                if in_name:
                    os.unlink(in_name)
                if out_name:
                    os.unlink(out_name)
                if err_name:
                    os.unlink(err_name)

            for out_line, err_line in self._combine(out_lines, err_lines):
                yield out_line and out_line.rstrip(), \
                      err_line and err_line.rstrip()

            if self.cwd:
                os.chdir(old_cwd)

    else: # posix

        def execute(self, timeout=None):
            import fcntl, popen2, select
            if self.cwd:
                old_cwd = os.getcwd()
                os.chdir(self.cwd)

            log.debug('Executing %s', [self.executable] + self.arguments)
            pipe = popen2.Popen3([self.executable] + self.arguments,
                                 capturestderr=True)
            if self.input:
                if not isinstance(self.input, basestring):
                    self.input = self.input.read()
            else:
                pipe.tochild.close()

            def make_non_blocking(filedesc):
                fileno = filedesc.fileno()
                flock = fcntl.fcntl(fileno, fcntl.F_GETFL)
                try:
                    fcntl.fcntl(fileno, fcntl.F_SETFL, flock | os.O_NDELAY)
                except AttributeError:
                    fcntl.fcntl(fileno, fcntl.F_SETFL, flock | os.FNDELAY)
                return filedesc

            out_file, err_file = [make_non_blocking(fd) for fd
                                  in (pipe.fromchild, pipe.childerr)]
            in_file = None
            if self.input:
                in_file = make_non_blocking(pipe.tochild)
            out_data, err_data = [], []
            out_eof = err_eof = False
            while not out_eof or not err_eof:
                to_check = [out_file] * (not out_eof) + \
                           [err_file] * (not err_eof)
                ready = select.select(to_check, in_file and [in_file] or [],
                                      [], timeout)
                if not (ready[0] or ready[1]):
                    raise TimeoutError, 'Command %s timed out' % self.executable
                if in_file in ready[1]:
                    sent = os.write(in_file.fileno(), self.input)
                    self.input = self.input[sent:]
                    if not self.input:
                        in_file.close()
                        in_file = None
                if out_file in ready[0]:
                    data = out_file.read()
                    if data:
                        out_data.append(data)
                    else:
                        out_eof = True
                if err_file in ready[0]:
                    data = err_file.read()
                    if data:
                        err_data.append(data)
                    else:
                        err_eof = True
                out_lines = self._extract_lines(out_data)
                err_lines = self._extract_lines(err_data)
                for out_line, err_line in self._combine(out_lines, err_lines):
                    yield out_line, err_line
                select.select([], [], [], .1)
            self.returncode = pipe.wait()
            log.debug('%s exited with code %s', self.executable,
                      self.returncode)

            if self.cwd:
                os.chdir(old_cwd)

    def _combine(self, *iterables):
        iterables = [iter(iterable) for iterable in iterables]
        size = len(iterables)
        while [iterable for iterable in iterables if iterable is not None]:
            to_yield = [None] * size
            for idx, iterable in enumerate(iterables):
                if iterable is None:
                    continue
                try:
                    to_yield[idx] = iterable.next()
                except StopIteration:
                    iterables[idx] = None
            yield tuple(to_yield)

    def _extract_lines(self, data):
        extracted = []
        def _endswith_linesep(string):
            for linesep in ('\n', '\r\n', '\r'):
                if string.endswith(linesep):
                    return True
        buf = ''.join(data)
        lines = buf.splitlines(True)
        if len(lines) > 1:
            extracted += lines[:-1]
            if _endswith_linesep(lines[-1]):
                extracted.append(lines[-1])
                buf = ''
            else:
                buf = lines[-1]
        elif _endswith_linesep(buf):
            extracted.append(buf)
            buf = ''
        data[:] = [buf]

        return [line.rstrip() for line in extracted]


class FileSet(object):
    """Utility class for collecting a list of files in a directory that match
    given name/path patterns."""

    DEFAULT_EXCLUDES = ['CVS/*', '*/CVS/*', '.svn/*', '*/.svn/*',
                        '.DS_Store', 'Thumbs.db']

    def __init__(self, basedir, include=None, exclude=None):
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
        for filename in self.files:
            yield filename

    def __contains__(self, filename):
        return filename in self.files
