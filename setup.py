#!/usr/bin/env python

from distutils.core import setup, Command
from bitten.distutils.testrunner import unittest

setup(name='bitten', version='1.0',
      packages=['bitten', 'bitten.general', 'bitten.python'],
      author="Christopher Lenz", author_email="cmlenz@gmx.de",
      url="http://projects.edgewall.com/bitten/",
      cmdclass={'unittest': unittest})
