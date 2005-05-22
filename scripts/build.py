#!/usr/bin/env python

from trac.core import ComponentManager

from bitten.recipe import RecipeExecutor
from bitten.python import cmd_distutils, rep_pylint
from bitten.general import cmd_make

if __name__ == '__main__':
    mgr = ComponentManager()
    executor = RecipeExecutor(mgr)
    executor.execute()
