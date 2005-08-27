# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import logging
import os
import shlex

from bitten.util import xmlio
from bitten.util.cmdline import Commandline

log = logging.getLogger('bitten.build.shtools')

def exec_(ctxt, executable=None, file_=None, output=None, args=None):
    """Execute a shell script."""
    assert executable or file_, \
        'Either "executable" or "file" attribute required'

    if args:
        args = shlex.split(args)
    else:
        args = []

    if executable is None:
        executable = file_
    elif file_:
        args[:0] = [file_]

    output_file = None
    if output:
        output = ctxt.resolve(output)
        output_file = file(output, 'w')

    try:
        cmdline = Commandline(executable, args, cwd=ctxt.basedir)
        log_elem = xmlio.Fragment()
        for out, err in cmdline.execute():
            if out is not None:
                log.info(out)
                xmlio.SubElement(log_elem, 'message', level='info')[out]
                if output:
                    output_file.write(out + os.linesep)
            if err is not None:
                log.error(err)
                xmlio.SubElement(log_elem, 'message', level='error')[err]
                if output:
                    output_file.write(err + os.linesep)
        ctxt.log(log_elem)
    finally:
        if output:
            output_file.close()

    if cmdline.returncode != 0:
        ctxt.error('Executing %s failed (%s)' % (file_, cmdline.returncode))

def pipe(ctxt, executable=None, file_=None, input_=None, output=None,
         args=None):
    """Pipe the contents of a file through a script."""
    assert file_, 'Missing required attribute "file"'
    assert input_, 'Missing required attribute "file"'

    if args:
        args = shlex.split(args)
    else:
        args = []

    if os.path.isfile(ctxt.resolve(file_)):
        file_ = ctxt.resolve(file_)

    if executable is None:
        executable = file_
    elif file_:
        args[:0] = [file_]

    input_file = file(ctxt.resolve(input_), 'r')

    output_file = None
    if output:
        output = ctxt.resolve(output)
        output_file = file(output, 'w')

    try:
        cmdline = Commandline(executable, args, stdin=input_file,
                              cwd=ctxt.basedir)
        log_elem = xmlio.Fragment()
        for out, err in cmdline.execute():
            if out is not None:
                log.info(out)
                xmlio.SubElement(log_elem, 'message', level='info')[out]
                if output:
                    output_file.write(out + os.linesep)
            if err is not None:
                log.error(err)
                xmlio.SubElement(log_elem, 'message', level='error')[err]
                if output:
                    output_file.write(err + os.linesep)
        ctxt.log(log_elem)
    finally:
        input_file.close()
        if output:
            output_file.close()

    if cmdline.returncode != 0:
        ctxt.error('Piping through %s failed (%s)' % (file_,
                   cmdline.returncode))
