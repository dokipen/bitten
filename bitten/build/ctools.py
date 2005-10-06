# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import logging

from bitten.build import CommandLine
from bitten.util import xmlio

log = logging.getLogger('bitten.build.ctools')

def configure(ctxt, file_='configure', enable=None, disable=None, with=None,
              without=None, cflags=None, cxxflags=None):
    """Run a configure script."""
    args = []
    if enable:
        args += ['--enable-%s' % feature for feature in enable.split()]
    if disable:
        args += ['--disable-%s' % feature for feature in disable.split()]
    if with:
        for pkg in with.split():
            pkg_path = pkg + '.path'
            if pkg_path in ctxt.config:
                args.append('--with-%s=%s' % (pkg, ctxt.config[pkg_path]))
            else:
                args.append('--with-%s' % pkg)
    if without:
        args += ['--without-%s' % pkg for pkg in without.split()]
    if cflags:
        args.append('CFLAGS=%s' % cflags)
    if cxxflags:
        args.append('CXXFLAGS=%s' % cxxflags)

    from bitten.build import shtools
    returncode = shtools.execute(ctxt, file_=file_, args=args)
    if returncode != 0:
        ctxt.error('configure failed (%s)' % cmdline.returncode)

def make(ctxt, target=None, file_=None, keep_going=False):
    """Execute a Makefile target."""
    args = ['--directory', ctxt.basedir]
    if file_:
        args += ['--file', ctxt.resolve(file_)]
    if keep_going:
        args.append('--keep-going')
    if target:
        args.append(target)

    from bitten.build import shtools
    returncode = shtools.execute(ctxt, executable='make', args=args)
    if returncode != 0:
        ctxt.error('make failed (%s)' % cmdline.returncode)
