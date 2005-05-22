import os

from trac.core import *
from trac.util import NaivePopen
from bitten import BuildError
from bitten.recipe import ICommandExecutor


class DistutilsExecutor(Component):
    implements(ICommandExecutor)

    def get_name(self):
        return 'distutils'

    def execute(self, basedir, command='build'):
        try:
            cmd = NaivePopen('python setup.py %s' % command)
            for line in cmd.out.splitlines():
                print '[distutils] %s' % line
        except OSError, e:
            raise BuildError, 'Executing distutils failed: %s' % e
