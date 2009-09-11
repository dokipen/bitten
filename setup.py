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

import os
import sys
from setuptools import setup, find_packages, Feature
from setuptools.command import egg_info

sys.path.append(os.path.join('doc', 'common'))
try:
    from doctools import build_doc, test_doc
except ImportError:
    build_doc = test_doc = None

# Turn off multiprocessing logging
# Bug in setuptools/distutils test runner using Python 2.6.2+?
import logging
if hasattr(logging, 'logMultiprocessing'):
    logging.logMultiprocessing = 0

NS_old = 'http://bitten.cmlenz.net/tools/'
NS_new = 'http://bitten.edgewall.org/tools/'
tools = [
        'sh#exec = bitten.build.shtools:exec_',
        'sh#pipe = bitten.build.shtools:pipe',
        'c#configure = bitten.build.ctools:configure',
        'c#autoreconf = bitten.build.ctools:autoreconf',
        'c#cppunit = bitten.build.ctools:cppunit',
        'c#cunit = bitten.build.ctools:cunit',
        'c#gcov = bitten.build.ctools:gcov',
        'c#make = bitten.build.ctools:make',
        'mono#nunit = bitten.build.monotools:nunit',
        'java#ant = bitten.build.javatools:ant',
        'java#junit = bitten.build.javatools:junit',
        'java#cobertura = bitten.build.javatools:cobertura',
        'php#phing = bitten.build.phptools:phing',
        'php#phpunit = bitten.build.phptools:phpunit',
        'php#coverage = bitten.build.phptools:coverage',
        'python#coverage = bitten.build.pythontools:coverage',
        'python#distutils = bitten.build.pythontools:distutils',
        'python#exec = bitten.build.pythontools:exec_',
        'python#figleaf = bitten.build.pythontools:figleaf',
        'python#pylint = bitten.build.pythontools:pylint',
        'python#trace = bitten.build.pythontools:trace',
        'python#unittest = bitten.build.pythontools:unittest',
        'svn#checkout = bitten.build.svntools:checkout',
        'svn#export = bitten.build.svntools:export',
        'svn#update = bitten.build.svntools:update',
        'hg#pull = bitten.build.hgtools:pull',
        'xml#transform = bitten.build.xmltools:transform'
    ]
recipe_commands = [NS_old + tool for tool in tools] \
                  + [NS_new + tool for tool in tools]

class MasterFeature(Feature):

    def exclude_from(self, dist):
        # Called when master is disabled (--without-master)
        pass

    def include_in(self, dist):
        # Called when master is enabled (default, or --with-master)
        dist.metadata.name = 'Bitten'
        dist.metadata.description = 'Continuous integration for Trac',
        dist.long_description = "A Trac plugin for collecting software " \
                                "metrics via continuous integration."""
        # Use full manifest when master is included
        egg_info.manifest_maker.template = "MANIFEST.in"
        # Include tests in source distribution
        if 'sdist' in dist.commands:
            dist.packages = find_packages()
        else:
            dist.packages = find_packages(exclude=['*tests*'])
        dist.test_suite = 'bitten.tests.suite'
        dist.package_data = {
              'bitten': ['htdocs/*.*',
                    'htdocs/charts_library/*.swf',
                    'templates/*.html',
                    'templates/*.txt']}
        dist.entry_points['trac.plugins'] = [
                    'bitten.admin = bitten.admin',
                    'bitten.main = bitten.main',
                    'bitten.master = bitten.master',
                    'bitten.web_ui = bitten.web_ui',
                    'bitten.testing = bitten.report.testing',
                    'bitten.coverage = bitten.report.coverage',
                    'bitten.lint = bitten.report.lint',
                    'bitten.notify = bitten.notify']

master = MasterFeature(
    description = "Bitten Master Trac plugin",
    standard = True,
    py_modules = [])

egg_info.manifest_maker.template = "MANIFEST-SLAVE.in"

if os.path.exists(os.path.join(os.path.dirname(__file__), 'MANIFEST.in')):
    available_features = {"master": master}
else:
    # Building from a slave distribution
    available_features = {}

setup(
    name = 'BittenSlave',
    version =  '0.7',
    author = 'Edgewall Software',
    author_email = 'info@edgewall.org',
    license = 'BSD',
    url = 'http://bitten.edgewall.org/',
    download_url = 'http://bitten.edgewall.org/wiki/Download',
    zip_safe = False,
    description = 'Continuous integration build slave for Trac',
    long_description = "A slave for running builds and submitting them to " \
                       "Bitten, the continuous integration system for Trac",
    packages = {},
    py_modules = ["bitten.__init__",
                  "bitten.build.__init__",
                  "bitten.build.api",
                  "bitten.build.config",
                  "bitten.build.ctools",
                  "bitten.build.hgtools",
                  "bitten.build.javatools",
                  "bitten.build.monotools",
                  "bitten.build.phptools",
                  "bitten.build.pythontools",
                  "bitten.build.shtools",
                  "bitten.build.svntools",
                  "bitten.build.xmltools",
                  "bitten.recipe",
                  "bitten.slave",
                  "bitten.util.__init__",
                  "bitten.util.loc",
                  "bitten.util.testrunner",
                  "bitten.util.xmlio",
                ],
    test_suite = 'bitten.slave_tests.suite',
    tests_require = [
        'figleaf',
    ],
    entry_points = {
        'console_scripts': [
            'bitten-slave = bitten.slave:main'
        ],
        'distutils.commands': [
            'unittest = bitten.util.testrunner:unittest'
        ],
        'bitten.recipe_commands': recipe_commands
    },
    features = available_features,
    cmdclass = {'build_doc': build_doc, 'test_doc': test_doc}
)
