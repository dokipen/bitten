# -*- coding: utf-8 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

"""Generic recipe commands for executing external processes."""

import logging
import os
import shlex

from bitten.build import CommandLine
from bitten.util import xmlio

log = logging.getLogger('bitten.build.shtools')

def exec_(ctxt, executable=None, file_=None, output=None, args=None):
    """Execute a program or shell script.
    
    @param ctxt: the build context
    @type ctxt: an instance of L{bitten.recipe.Context}
    @param executable: name of the executable to run
    @param file_: name of the script file, relative to the project directory,
        that should be run
    @param output: name of the file to which the output of the script should be
        written
    @param args: command-line arguments to pass to the script
    """
    assert executable or file_, \
        'Either "executable" or "file" attribute required'

    returncode = execute(ctxt, executable=executable, file_=file_,
                         output=output, args=args)
    if returncode != 0:
        ctxt.error('Executing %s failed (error code %s)' % (executable or file_,
                                                            returncode))

def pipe(ctxt, executable=None, file_=None, input_=None, output=None,
         args=None):
    """Pipe the contents of a file through a program or shell script.
    
    @param ctxt: the build context
    @type ctxt: an instance of L{bitten.recipe.Context}
    @param executable: name of the executable to run
    @param file_: name of the script file, relative to the project directory,
        that should be run
    @param input_: name of the file containing the data that should be passed
        to the shell script on its standard input stream
    @param output: name of the file to which the output of the script should be
        written
    @param args: command-line arguments to pass to the script
    """
    assert executable or file_, \
        'Either "executable" or "file" attribute required'
    assert input_, 'Missing required attribute "input"'

    returncode = execute(ctxt, executable=executable, file_=file_,
                         input_=input_, output=output, args=args)
    if returncode != 0:
        ctxt.error('Piping through %s failed (error code %s)'
                   % (executable or file_, returncode))

def execute(ctxt, executable=None, file_=None, input_=None, output=None,
            args=None):
    """Generic external program execution.
    
    This function is not itself bound to a recipe command, but rather used from
    other commands.
    
    @param ctxt: the build context
    @type ctxt: an instance of L{bitten.recipe.Context}
    @param executable: name of the executable to run
    @param file_: name of the script file, relative to the project directory,
        that should be run
    @param input_: name of the file containing the data that should be passed
        to the shell script on its standard input stream
    @param output: name of the file to which the output of the script should be
        written
    @param args: command-line arguments to pass to the script
    """
    if args:
        if isinstance(args, basestring):
            args = shlex.split(args)
    else:
        args = []

    if file_ and os.path.isfile(ctxt.resolve(file_)):
        file_ = ctxt.resolve(file_)

    if executable is None:
        executable = file_
    elif file_:
        args[:0] = [file_]

    if input_:
        input_file = file(ctxt.resolve(input_), 'r')
    else:
        input_file = None

    output_file = None
    if output:
        output = ctxt.resolve(output)
        output_file = file(output, 'w')

    try:
        cmdline = CommandLine(executable, args, input=input_file,
                              cwd=ctxt.basedir)
        log_elem = xmlio.Fragment()
        for out, err in cmdline.execute():
            if out is not None:
                log.info(out)
                log_elem.append(xmlio.Element('message', level='info')[
                    out.replace(ctxt.basedir + os.sep, '')
                       .replace(ctxt.basedir, '')
                ])
                if output:
                    output_file.write(out + os.linesep)
            if err is not None:
                log.error(err)
                log_elem.append(xmlio.Element('message', level='error')[
                    err.replace(ctxt.basedir + os.sep, '')
                       .replace(ctxt.basedir, '')
                ])
                if output:
                    output_file.write(err + os.linesep)
        ctxt.log(log_elem)
    finally:
        if input_:
            input_file.close()
        if output:
            output_file.close()

    return cmdline.returncode
