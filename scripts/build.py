#!/usr/bin/env python

import sys

from bitten import BuildError
from bitten.recipe import Recipe

def build():
    step_id = None
    if len(sys.argv) > 1:
        step_id = sys.argv[1]

    recipe = Recipe()
    steps_run = []
    for step in recipe:
        if not step_id or step.id == step_id:
            print '-->', step.description or step.id
            for function, kw in step:
                function(recipe.basedir, **kw)
            print
            steps_run.append(step.id)

    if step_id and not step_id in steps_run:
        raise BuildError, "Recipe has no step named '%s'" % step_id

if __name__ == '__main__':
    try:
        build()
    except BuildError, e:
        print>>sys.stderr, "FAILED: %s" % e
        sys.exit(-1)
