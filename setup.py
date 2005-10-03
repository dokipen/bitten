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

NS = 'http://bitten.cmlenz.net/tools/'

setup(
    name='Bitten', version=VERSION, author='Christopher Lenz',
    author_email='cmlenz@gmx.de', url='http://bitten.cmlenz.net/',
    description='Framework for collecting software metrics via continuous '
                'integration',
    license='BSD',
    packages=find_packages(exclude=['ez_setup', '*.tests*']),
    package_data={
        'bitten.trac_ext': ['htdocs/*.*',
                            'htdocs/charts_library/*.swf',
                            'templates/*.cs']
    },
    entry_points = {
        'console_scripts': [
            'bitten-master = bitten.master:main',
            'bitten-slave = bitten.slave:main'
        ],
        'distutils.commands': [
            'unittest = bitten.util.testrunner:unittest'
        ],
        'trac.plugins': [
            'bitten.main = bitten.trac_ext.main',
            'bitten.web_ui = bitten.trac_ext.web_ui',
            'bitten.summarizers = bitten.trac_ext.summarizers',
            'bitten.charts = bitten.trac_ext.charts'
        ],
        'bitten.recipe_commands': [
            NS + 'sh#exec = bitten.build.shtools:exec_',
            NS + 'sh#pipe = bitten.build.shtools:pipe',
            NS + 'c#configure = bitten.build.ctools:configure',
            NS + 'c#make = bitten.build.ctools:make',
            NS + 'java#ant = bitten.build.javatools:ant',
            NS + 'python#distutils = bitten.build.pythontools:distutils',
            NS + 'python#exec = bitten.build.pythontools:exec_',
            NS + 'python#pylint = bitten.build.pythontools:pylint',
            NS + 'python#trace = bitten.build.pythontools:trace',
            NS + 'python#unittest = bitten.build.pythontools:unittest',
            NS + 'x#transform = bitten.build.xmltools:transform'
        ]
    },
    test_suite='bitten.tests.suite', zip_safe=True
)
