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

def cppunit(ctxt, file_=None, srcdir=None):
    """Collect CppUnit XML data."""
    assert file_, 'Missing required attribute "file"'

    try:
        fileobj = file(ctxt.resolve(file_), 'r')
        try:
            total, failed = 0, 0
            results = xmlio.Fragment()
            for group in xmlio.parse(fileobj):
                if group.name not in ('FailedTests', 'SuccessfulTests'):
                    continue
                for child in group.children():
                    test = xmlio.Element('test')
                    name = child.children('Name').next().gettext()
                    if '::' in name:
                        parts = name.split('::')
                        test.attr['fixture'] = '::'.join(parts[:-1])
                        name = parts[-1]
                    test.attr['name'] = name

                    for location in child.children('Location'):
                        for file_elem in location.children('File'):
                            filepath = file_elem.gettext()
                            if srcdir is not None:
                                filepath = posixpath.join(srcdir, filepath)
                            test.attr['file'] = filepath
                            break
                        for line_elem in location.children('Line'):
                            test.attr['line'] = line_elem.gettext()
                            break
                        break

                    if child.name == 'FailedTest':
                        for message in child.children('Message'):
                            test.append(xmlio.Element('traceback')[
                                message.gettext()
                            ])
                        test.attr['status'] = 'failure'
                        failed += 1
                    else:
                        test.attr['status'] = 'success'

                    results.append(test)
                    total += 1

            if failed:
                ctxt.error('%d of %d test%s failed' % (failed, total,
                           total != 1 and 's' or ''))

            ctxt.report('test', results)

        finally:
            fileobj.close()

    except IOError, e:
        log.warning('Error opening CppUnit results file (%s)', e)
    except xmlio.ParseError, e:
        print e
        log.warning('Error parsing CppUnit results file (%s)', e)
