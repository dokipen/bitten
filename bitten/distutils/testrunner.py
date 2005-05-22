import re
import sys
import time
from distutils.core import Command
from unittest import _TextTestResult, TextTestRunner

from elementtree.ElementTree import Element, ElementTree, SubElement


class XMLTestResult(_TextTestResult):

    def __init__(self, stream, descriptions, verbosity):
        _TextTestResult.__init__(self, stream, descriptions, verbosity)
        self.tests = []

    def startTest(self, test):
        _TextTestResult.startTest(self, test)
        filename = sys.modules[test.__module__].__file__
        if filename.endswith('.pyc') or filename.endswith('.pyo'):
            filename = filename[:-1]
        self.tests.append([test, filename, time.time()])

    def stopTest(self, test):
        _TextTestResult.stopTest(self, test)
        self.tests[-1][-1] = time.time() - self.tests[-1][-1]


class XMLTestRunner(TextTestRunner):

    def __init__(self, stream=sys.stderr, xml_stream=None):
        TextTestRunner.__init__(self, stream, descriptions=0, verbosity=1)
        self.xml_stream = xml_stream

    def _makeResult(self):
        return XMLTestResult(self.stream, self.descriptions, self.verbosity)

    def run(self, test):
        result = TextTestRunner.run(self, test)

        if not self.xml_stream:
            return result

        root = Element('unittest-results')
        for testcase, filename, timetaken in result.tests:
            status = 'success'
            tb = None
            
            if testcase in [e[0] for e in result.errors]:
                status = 'error'
                tb = [e[1] for e in result.errors if e[0] is testcase][0]
            elif testcase in [f[0] for f in result.failures]:
                status = 'failure'
                tb = [f[1] for f in result.failures if f[0] is testcase][0]

            test_elem = SubElement(root, 'test', file=filename,
                                   name=str(testcase), status=status,
                                   duration=str(timetaken))

            description = testcase.shortDescription()
            if description:
                desc_elem = SubElement(test_elem, 'description')
                desc_elem.test = description

            if tb:
                tb_elem = SubElement(test_elem, 'traceback')
                tb_elem.text = tb

        ElementTree(root).write(self.xml_stream)
        return result


class unittest(Command):
    description = "Runs the unit tests, and optionally records code coverage"
    user_options = [('test-suite=', 's',
                     'Name of the unittest suite to run'),
                    ('xml-output=', None,
                     'Path of the XML file where test results are written to'),
                    ('coverage-dir=', None,
                     'Directory where coverage files are to be stored'),
                     ('coverage-results=', None,
                     'Name of the file where the coverage summary should be stored')]

    def initialize_options(self):
        self.test_suite = None
        self.xml_results = None
        self.coverage_results = None
        self.coverage_dir = None

    def finalize_options(self):
        assert self.test_suite, 'Missing required attribute "test-suite"'
        if self.xml_results is not None:
            self.xml_results = open(self.xml_results, 'w')

    def run(self):
        if self.coverage_dir:
            from trace import Trace
            trace = Trace(ignoredirs=[sys.prefix, sys.exec_prefix],
                          trace=False, count=True)
            trace.runfunc(self._run_tests)
            # make a report, telling it where you want output
            results = trace.results()
            real_stdout = sys.stdout
            sys.stdout = open(self.coverage_results, 'w')
            try:
                results.write_results(show_missing=True, summary=True,
                                      coverdir=self.coverage_dir)
            finally:
                sys.stdout.close()
                sys.stdout = real_stdout
        else:
            self._run_tests()

    def _run_tests(self):
        import unittest
        suite = __import__(self.test_suite)
        for comp in self.test_suite.split('.')[1:]:
            suite = getattr(suite, comp)
        runner = XMLTestRunner(stream=sys.stderr, xml_stream=self.xml_results)
        runner.run(suite.suite())
