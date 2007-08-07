#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2007 Edgewall Software
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

from setuptools import setup, find_packages

from bitten.util.testrunner import unittest

NS = 'http://bitten.cmlenz.net/tools/'

setup(
    name = 'Bitten',
    version = '0.6',
    description = 'Continuous integration for Trac',
    long_description = \
"""A Trac plugin for collecting software metrics via continuous integration.""",
    author = 'Edgewall Software',
    author_email = 'info@edgewall.org',
    license = 'BSD',
    url = 'http://bitten.edgewall.org/',
    download_url = 'http://bitten.edgewall.org/wiki/Download',
    zip_safe = False,

    packages=find_packages(exclude=['*.tests*']),
    package_data={
        'bitten.trac_ext': ['htdocs/*.*',
                            'htdocs/charts_library/*.swf',
                            'templates/*.cs']
    },
    test_suite='bitten.tests.suite',
    entry_points = {
        'console_scripts': [
            'bitten-slave = bitten.slave:main'
        ],
        'distutils.commands': [
            'unittest = bitten.util.testrunner:unittest'
        ],
        'trac.plugins': [
            'bitten.main = bitten.trac_ext.main',
            'bitten.master = bitten.master',
            'bitten.web_ui = bitten.trac_ext.web_ui',
            'bitten.testing = bitten.report.testing',
            'bitten.coverage = bitten.report.coverage'
        ],
        'bitten.recipe_commands': [
            NS + 'sh#exec = bitten.build.shtools:exec_',
            NS + 'sh#pipe = bitten.build.shtools:pipe',
            NS + 'c#configure = bitten.build.ctools:configure',
            NS + 'c#cppunit = bitten.build.ctools:cppunit',
            NS + 'c#gcov = bitten.build.ctools:gcov',
            NS + 'c#make = bitten.build.ctools:make',
            NS + 'java#ant = bitten.build.javatools:ant',
            NS + 'java#junit = bitten.build.javatools:junit',
            NS + 'java#cobertura = bitten.build.javatools:cobertura',
            NS + 'python#distutils = bitten.build.pythontools:distutils',
            NS + 'python#exec = bitten.build.pythontools:exec_',
            NS + 'python#pylint = bitten.build.pythontools:pylint',
            NS + 'python#trace = bitten.build.pythontools:trace',
            NS + 'python#unittest = bitten.build.pythontools:unittest',
            NS + 'svn#checkout = bitten.build.svntools:checkout',
            NS + 'svn#export = bitten.build.svntools:export',
            NS + 'svn#update = bitten.build.svntools:update',
            NS + 'xml#transform = bitten.build.xmltools:transform'
        ]
    },

    cmdclass = {'unittest': unittest}
)
