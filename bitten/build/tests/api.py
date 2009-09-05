# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import os
import shutil
import sys
import tempfile
import unittest

from bitten.build import CommandLine, FileSet, TimeoutError, BuildError


class CommandLineTestCase(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.realpath(tempfile.mkdtemp(suffix='bitten_test'))

    def tearDown(self):
        shutil.rmtree(self.basedir)

    def _create_file(self, name, content=None):
        filename = os.path.join(self.basedir, name)
        fd = file(filename, 'w')
        if content:
            fd.write(content)
        fd.close()
        return filename

    def test_escape_and_quote_args(self):
        # Verify shlex.split() used by many commands to split input -> args
        import shlex
        self.assertEquals(['o\ne', '4 2', '"hi there"'],
                shlex.split('o\\\ne "4 2" \\"hi\\ there\\"'))

    def test_single_argument(self):
        cmdline = CommandLine(sys.executable, ['-V'])
        stdout = []
        stderr = []
        for out, err in cmdline.execute(timeout=5.0):
            if out is not None:
                stdout.append(out)
            if err is not None:
                stderr.append(err)
        py_version = '.'.join([str(v) for (v) in sys.version_info[:3]]
                                                            ).rstrip('.0')

        self.assertEqual(['Python %s' % py_version], stderr)
        self.assertEqual([], stdout)
        self.assertEqual(0, cmdline.returncode)

    def test_multiple_arguments(self):
        script_file = self._create_file('test.py', content="""
import sys
for arg in sys.argv[1:]:
    print arg
""")
        cmdline = CommandLine('python', [script_file, 'foo', 'bar', 'baz'])
        stdout = []
        stderr = []
        for out, err in cmdline.execute(timeout=5.0):
            stdout.append(out)
            stderr.append(err)
        self.assertEqual(['foo', 'bar', 'baz'], stdout)
        self.assertEqual([None, None, None], stderr)
        self.assertEqual(0, cmdline.returncode)

    def test_output_error_streams(self):
        script_file = self._create_file('test.py', content="""
import sys, time
print>>sys.stdout, 'Hello'
print>>sys.stdout, 'world!'
sys.stdout.flush()
time.sleep(.1)
print>>sys.stderr, 'Oops'
sys.stderr.flush()
""")
        cmdline = CommandLine('python', [script_file])
        stdout = []
        stderr = []
        for out, err in cmdline.execute(timeout=5.0):
            stdout.append(out)
            stderr.append(err)
        py_version = '.'.join([str(v) for (v) in sys.version_info[:3]])
        self.assertEqual(['Hello', 'world!', None], stdout)
        self.assertEqual(0, cmdline.returncode)

    def test_input_stream_as_fileobj(self):
        script_file = self._create_file('test.py', content="""
import sys
data = sys.stdin.read()
if data == 'abcd':
    print>>sys.stdout, 'Thanks'
""")
        input_file = self._create_file('input.txt', content='abcd')
        input_fileobj = file(input_file, 'r')
        try:
            cmdline = CommandLine('python', [script_file], input=input_fileobj)
            stdout = []
            stderr = []
            for out, err in cmdline.execute(timeout=5.0):
                stdout.append(out)
                stderr.append(err)
            py_version = '.'.join([str(v) for (v) in sys.version_info[:3]])
            self.assertEqual(['Thanks'], stdout)
            self.assertEqual([None], stderr)
            self.assertEqual(0, cmdline.returncode)
        finally:
            input_fileobj.close()

    def test_input_stream_as_string(self):
        script_file = self._create_file('test.py', content="""
import sys
data = sys.stdin.read()
if data == 'abcd':
    print>>sys.stdout, 'Thanks'
""")
        cmdline = CommandLine('python', [script_file], input='abcd')
        stdout = []
        stderr = []
        for out, err in cmdline.execute(timeout=5.0):
            stdout.append(out)
            stderr.append(err)
        py_version = '.'.join([str(v) for (v) in sys.version_info[:3]])
        self.assertEqual(['Thanks'], stdout)
        self.assertEqual([None], stderr)
        self.assertEqual(0, cmdline.returncode)

    def test_timeout(self):
        script_file = self._create_file('test.py', content="""
import time
time.sleep(2.0)
print 'Done'
""")
        cmdline = CommandLine('python', [script_file])
        iterable = iter(cmdline.execute(timeout=.5))
        self.assertRaises(TimeoutError, iterable.next)

    def test_nonexisting_command(self):
        cmdline = CommandLine('doesnotexist', [])
        iterable = iter(cmdline.execute())
        try:
            out, err = iterable.next()
            self.fail("Expected BuildError")
        except BuildError, e:
            self.failUnless("Error executing ['doesnotexist']" in str(e))

class FileSetTestCase(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.realpath(tempfile.mkdtemp(suffix='bitten_test'))

    def tearDown(self):
        shutil.rmtree(self.basedir)

    # Convenience methods

    def _create_dir(self, *path):
        cur = self.basedir
        for part in path:
            cur = os.path.join(cur, part)
            os.mkdir(cur)
        return cur[len(self.basedir) + 1:]

    def _create_file(self, *path):
        filename = os.path.join(self.basedir, *path)
        fd = file(filename, 'w')
        fd.close()
        return filename[len(self.basedir) + 1:]

    # Test methods

    def test_empty(self):
        fileset = FileSet(self.basedir)
        self.assertRaises(StopIteration, iter(fileset).next)

    def test_top_level_files(self):
        foo_txt = self._create_file('foo.txt')
        bar_txt = self._create_file('bar.txt')
        fileset = FileSet(self.basedir)
        assert foo_txt in fileset and bar_txt in fileset

    def test_files_in_subdir(self):
        self._create_dir('tests')
        foo_txt = self._create_file('tests', 'foo.txt')
        bar_txt = self._create_file('tests', 'bar.txt')
        fileset = FileSet(self.basedir)
        assert foo_txt in fileset and bar_txt in fileset

    def test_files_in_subdir_with_include(self):
        self._create_dir('tests')
        foo_txt = self._create_file('tests', 'foo.txt')
        bar_txt = self._create_file('tests', 'bar.txt')
        fileset = FileSet(self.basedir, include='tests/*.txt')
        assert foo_txt in fileset and bar_txt in fileset

    def test_files_in_subdir_with_exclude(self):
        self._create_dir('tests')
        foo_txt = self._create_file('tests', 'foo.txt')
        bar_txt = self._create_file('tests', 'bar.txt')
        fileset = FileSet(self.basedir, include='tests/*.txt', exclude='bar.*')
        assert foo_txt in fileset and bar_txt not in fileset


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(CommandLineTestCase, 'test'))
    suite.addTest(unittest.makeSuite(FileSetTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
