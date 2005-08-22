# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
#
# Bitten is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Trac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Christopher Lenz <cmlenz@gmx.de>

import logging
import os
import shlex
import shutil
import time

log = logging.getLogger('bitten.cmdline')


class TimeoutError(Exception):
    """Exception raised when the execution of a command times out."""


class Commandline(object):
    """Simple helper for executing subprocesses."""
    # TODO: Use 'subprocess' module if available (Python >= 2.4)

    def __init__(self, executable, args, input=None, cwd=None):
        """Initialize the Commandline object.
        
        @param executable The name of the program to execute
        @param args A list of arguments to pass to the executable
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

        # TODO: On windows, map file name extension to application
        if os.name == 'nt':
            pass

        # Shebang support for Posix systems
        if os.path.isfile(self.executable):
            executable_file = file(self.executable, 'r')
            try:
                for line in executable_file:
                    if line.startswith('#!'):
                        parts = shlex.split(line[2:])
                        if len(parts) > 1:
                            self.arguments[:0] = parts[1:] + [self.executable]
                        else:
                            self.arguments[:0] = [self.executable]
                        self.executable = parts[0]
                    break
            finally:
                executable_file.close()

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
            out_name = tempfile.mktemp()
            err_name = tempfile.mktemp()
            cmd = "( %s ) > %s 2> %s" % (' '.join(args), out_name, err_name)
            self.returncode = os.system(cmd)
            log.debug('Exited with code %s', self.returncode)

            out_file = file(out_name, 'r')
            err_file = file(err_name, 'r')
            out_lines = out_file.readlines()
            err_lines = err_file.readlines()
            out_file.close()
            err_file.close()
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
                if isinstance(self.input, basestring):
                    pipe.tochild.write(self.input)
                else:
                    shutil.copyfileobj(self.input, pipe.tochild)
            pipe.tochild.close()

            def make_non_blocking(fd):
                fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                try:
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NDELAY)
                except AttributeError:
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.FNDELAY)

            out_file, err_file = pipe.fromchild, pipe.childerr
            map(make_non_blocking, [out_file.fileno(), err_file.fileno()])
            out_data, err_data = [], []
            out_eof = err_eof = False
            while not out_eof or not err_eof:
                to_check = [out_file] * (not out_eof) + [err_file] * (not err_eof)
                ready = select.select(to_check, [], [], timeout)
                if not ready[0]:
                    raise TimeoutError, 'Command %s timed out' % self.executable
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
                time.sleep(.1)
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
