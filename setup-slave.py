#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2007 Edgewall Software
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2005-2007 David Fraser <davidf@sjsoft.com>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

from setuptools import setup as setup_slave
from setuptools.command import egg_info

from setup import recipe_commands, shared_args

# TODO: there must be a way to pass this altered value in...
egg_info.manifest_maker.template = "MANIFEST-SLAVE.in"

if __name__ == '__main__':
    setup_slave(
        name = 'Bitten-Slave',
        description = 'Continuous integration build slave for Trac',
        long_description = \
    """A slave for running builds and submitting them to Bitten, the continuous integration system for Trac""",

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
                      "bitten.build.tests.__init__",
                      "bitten.build.tests.api",
                      "bitten.build.tests.config",
                      "bitten.build.tests.ctools",
                      "bitten.build.tests.dummy",
                      "bitten.build.tests.hgtools",
                      "bitten.build.tests.javatools",
                      "bitten.build.tests.monotools",
                      "bitten.build.tests.phptools",
                      "bitten.build.tests.pythontools",
                      "bitten.build.tests.xmltools",
                      "bitten.build.xmltools",
                      "bitten.recipe",
                      "bitten.slave",
                      "bitten.slave_tests.__init__",
                      "bitten.slave_tests.recipe",
                      "bitten.slave_tests.slave",
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
                'bitten-slave = bitten.slave:main',
            ],
            'distutils.commands': [
                'unittest = bitten.util.testrunner:unittest',
            ],
            'bitten.recipe_commands': recipe_commands
        },
        
        **shared_args
    )
