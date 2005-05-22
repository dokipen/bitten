from distutils.core import setup, Command
from bitten.distutils.testrunner import test

setup(name='bitten', version='1.0',
      packages=['bitten', 'bitten.general', 'bitten.python'],
      cmdclass={'test': test})
