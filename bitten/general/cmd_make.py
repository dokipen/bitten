import os

from trac.core import *
from trac.util import NaivePopen
from bitten import BuildError
from bitten.recipe import ICommandExecutor


class MakeExecutor(Component):
    implements(ICommandExecutor)

    def get_name(self):
        return 'make'

    def execute(self, basedir, target='all'):
        cmd = NaivePopen('make %s' % target, capturestderr=True)
        for line in cmd.out.splitlines():
            print '[make] %s' % line
