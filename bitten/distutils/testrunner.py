import sys
import time
from distutils.core import Command
from unittest import _TextTestResult, TextTestRunner

from elementtree.ElementTree import Element, ElementTree, SubElement


class FullTestResult(_TextTestResult):

    def __init__(self, stream, descriptions, verbosity):
        _TextTestResult.__init__(self, stream, descriptions, verbosity)
        self.tests = []

    def startTest(self, test):
        _TextTestResult.startTest(self, test)
        self.tests.append([test,
                           sys.modules[test.__module__].__file__,
                           time.time()])

    def stopTest(self, test):
        _TextTestResult.stopTest(self, test)
        self.tests[-1][-1] = time.time() - self.tests[-1][-1]


class XMLTestRunner(TextTestRunner):

    def __init__(self, stream=sys.stderr, xml_stream=None):
        TextTestRunner.__init__(self, stream, descriptions=0, verbosity=1)
        self.xml_stream = xml_stream

    def _makeResult(self):
        return FullTestResult(self.stream, self.descriptions, self.verbosity)

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


class test(Command):
    description = "Runs the unit tests"
    user_options = [('test-suite=', 's',
                     'Name of the unittest suite to run'),
                    ('xml-output=', None,
                     'Path of the XML file where test results are written to')]

    def initialize_options(self):
        self.test_suite = None
        self.xml_output = None
        self.test_descriptions = None

    def finalize_options(self):
        assert self.test_suite, 'Missing required attribute "test-suite"'
        if self.xml_output is not None:
            self.xml_output = open(self.xml_output, 'w')

    def run(self):
        import unittest
        suite = __import__(self.test_suite)
        for comp in self.test_suite.split('.')[1:]:
            suite = getattr(suite, comp)
        runner = XMLTestRunner(stream=sys.stderr, xml_stream=self.xml_output)
        runner.run(suite.suite())
