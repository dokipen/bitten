#!/usr/bin/env python

from trac.core import ComponentManager

from bitten.recipe import Recipe, RecipeExecutor
from bitten.python import cmd_distutils, rep_pylint, rep_unittest, rep_trace
from bitten.general import cmd_make

if __name__ == '__main__':
    mgr = ComponentManager()
    recipe = Recipe()
    RecipeExecutor(mgr).execute(recipe)
