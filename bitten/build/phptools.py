# -*- coding: UTF-8 -*-
#
# Copyright (C) 2007 Edgewall Software
# Copyright (C) 2007 Wei Zhuo <weizhuo@gmail.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import logging
import os
import shlex

from bitten.util import xmlio
from bitten.build import shtools

log = logging.getLogger('bitten.build.phptools')

def phing(ctxt, file_=None, target=None, executable=None, args=None):
    """Run a phing build"""
    if args:
        args = shlex.split(args)
    else:
        args = []
    args += ['-logger', 'phing.listener.DefaultLogger',
             '-buildfile', ctxt.resolve(file_ or 'build.xml')]
    if target:
        args.append(target)

    returncode = shtools.execute(ctxt, file_=executable or 'phing', args=args)
    if returncode != 0:
        ctxt.error('Phing failed (%s)' % returncode)

def phpunit(ctxt, file_=None):
    """Extract test results from a PHPUnit XML report."""
    assert file_, 'Missing required attribute "file"'

    def _process_testsuite(testsuite, results, parent_file=''):
        for testcase in testsuite.children():
            if testcase.name == 'testsuite':
                _process_testsuite(testcase, results,
                        parent_file=testcase.attr.get('file', parent_file))
                continue
            test = xmlio.Element('test')
            test.attr['fixture'] = testsuite.attr['name']
            test.attr['name'] = testcase.attr['name']
            test.attr['duration'] = testcase.attr['time']
            result = list(testcase.children())
            if result:
                test.append(xmlio.Element('traceback')[
                    result[0].gettext()
                ])
                test.attr['status'] = result[0].name
            else:
                test.attr['status'] = 'success'
            if 'file' in testsuite.attr or parent_file:
                testfile = os.path.realpath(
                                    testsuite.attr.get('file', parent_file))
                if testfile.startswith(ctxt.basedir):
                    testfile = testfile[len(ctxt.basedir) + 1:]
                testfile = testfile.replace(os.sep, '/')
                test.attr['file'] = testfile
            results.append(test)

    try:
        total, failed = 0, 0
        results = xmlio.Fragment()
        fileobj = file(ctxt.resolve(file_), 'r')
        try:
            for testsuite in xmlio.parse(fileobj).children('testsuite'):
                total += int(testsuite.attr['tests'])
                failed += int(testsuite.attr['failures']) + \
                            int(testsuite.attr['errors'])

                _process_testsuite(testsuite, results)
        finally:
            fileobj.close()
        if failed:
            ctxt.error('%d of %d test%s failed' % (failed, total,
                        total != 1 and 's' or ''))
        ctxt.report('test', results)
    except IOError, e:
        ctxt.log('Error opening PHPUnit results file (%s)' % e)
    except xmlio.ParseError, e:
        ctxt.log('Error parsing PHPUnit results file (%s)' % e)

def coverage(ctxt, file_=None):
    """Extract data from Phing or PHPUnit code coverage report."""
    assert file_, 'Missing required attribute "file"'

    def _process_phing_coverage(ctxt, element, coverage):
        for cls in element.children('class'):
            statements = float(cls.attr['statementcount'])
            covered = float(cls.attr['statementscovered'])
            if statements:
                percentage = covered / statements * 100
            else:
                percentage = 100
            class_coverage = xmlio.Element('coverage',
                name=cls.attr['name'],
                lines=int(statements),
                percentage=percentage
            )
            source = list(cls.children())[0]
            if 'sourcefile' in source.attr:
                sourcefile = os.path.realpath(source.attr['sourcefile'])
                if sourcefile.startswith(ctxt.basedir):
                    sourcefile = sourcefile[len(ctxt.basedir) + 1:]
                sourcefile = sourcefile.replace(os.sep, '/')
                class_coverage.attr['file'] = sourcefile
            coverage.append(class_coverage)

    def _process_phpunit_coverage(ctxt, element, coverage):
        for cls in element._node.getElementsByTagName('class'):
            sourcefile = cls.parentNode.getAttribute('name')
            if not os.path.isabs(sourcefile):
                sourcefile = os.path.join(ctxt.basedir, sourcefile)
            if sourcefile.startswith(ctxt.basedir):
                loc, ncloc = 0, 0.0
                for line in cls.parentNode.getElementsByTagName('line'):
                    if str(line.getAttribute('type')) == 'stmt':
                        loc += 1
                        if int(line.getAttribute('count')) == 0:
                            ncloc += 1
                if loc > 0:
                    percentage = 100 - (ncloc / loc * 100)
                else:
                    percentage = 100

                if sourcefile.startswith(ctxt.basedir):
                    sourcefile = sourcefile[len(ctxt.basedir) + 1:]
                class_coverage = xmlio.Element('coverage',
                                    name=cls.getAttribute('name'),
                                    lines=int(loc),
                                    percentage=int(percentage),
                                    file=sourcefile.replace(os.sep, '/'))
                coverage.append(class_coverage)

    try:
        summary_file = file(ctxt.resolve(file_), 'r')
        summary = xmlio.parse(summary_file)
        coverage = xmlio.Fragment()
        try:
            for element in summary.children():
                if element.name == 'package':
                    _process_phing_coverage(ctxt, element, coverage)
                elif element.name == 'project':
                    _process_phpunit_coverage(ctxt, element, coverage)
        finally:
            summary_file.close()
        ctxt.report('coverage', coverage)
    except IOError, e:
        ctxt.log('Error opening coverage summary file (%s)' % e)
    except xmlio.ParseError, e:
        ctxt.log('Error parsing coverage summary file (%s)' % e)
