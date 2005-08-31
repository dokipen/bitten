#!/usr/bin/env python
# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

from setuptools import setup, find_packages

from bitten import __version__ as VERSION
from bitten.util.testrunner import unittest

setup(name='bitten', version=VERSION, author='Christopher Lenz',
      author_email='cmlenz@gmx.de', url='http://bitten.cmlenz.net/',
      description='Framework for collecting software metrics via continuous '
                  'integration',
      license='BSD',
      packages=find_packages(exclude=['ez_setup', '*.tests*']),
      package_data={'bitten.trac_ext': ['htdocs/*.*', 'htdocs/charts/*.swf',
                                        'templates/*.cs']},
      scripts=['scripts/bitten', 'scripts/bittend'],
      test_suite='bitten.tests.suite', zip_safe=True,
      cmdclass={'unittest': unittest})
