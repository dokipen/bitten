# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import keyword
import logging
import os

from bitten.build import BuildError
from bitten.util import xmlio

__all__ = ['Recipe']

log = logging.getLogger('bitten.recipe')


class InvalidRecipeError(Exception):
    """Exception raised when a recipe cannot be processed."""


class Context(object):
    """The context in which a recipe command or report is run."""

    current_step = None
    current_function = None

    def __init__(self, basedir):
        self.basedir = os.path.realpath(basedir)
        self.output = []

    def error(self, message):
        self.output.append((Recipe.ERROR, self.current_function, message))

    def log(self, xml_elem):
        self.output.append((Recipe.LOG, self.current_function, xml_elem))

    def report(self, xml_elem):
        self.output.append((Recipe.REPORT, self.current_function, xml_elem))

    def resolve(self, *path):
        return os.path.normpath(os.path.join(self.basedir, *path))


class Step(object):
    """Represents a single step of a build recipe.

    Iterate over an object of this class to get the commands to execute, and
    their keyword arguments.
    """

    def __init__(self, elem):
        self._elem = elem
        self.id = elem.attr['id']
        self.description = elem.attr.get('description')
        self.onerror = elem.attr.get('onerror', 'fail')

    def __iter__(self):
        for child in self._elem:
            if child.namespace: # Commands
                yield self._function(child), self._args(child)
            elif child.name == 'reports': # Reports
                for grandchild in child:
                    yield self._function(grandchild), self._args(grandchild)
            else:
                raise InvalidRecipeError, "Unknown element <%s>" % child.name

    def execute(self, ctxt):
        ctxt.current_step = self
        try:
            for function, args in self:
                ctxt.current_function = function.__name__
                function(ctxt, **args)
                ctxt.current_function = None
        finally:
            ctxt.current_step = None
        errors = []
        while ctxt.output:
            type, function, output = ctxt.output.pop(0)
            yield type, function, output
            if type == Recipe.ERROR:
                errors.append((function, output))
        if errors:
            if self.onerror == 'fail':
                raise BuildError, 'Build step %s failed' % self.id
            log.warning('Ignoring errors in step %s (%s)', self.id,
                        ', '.join([error[1] for error in errors]))

    def _args(self, elem):
        return dict([(self._translate_name(name), value) for name, value
                     in elem.attr.items()])

    def _function(self, elem):
        if not elem.namespace.startswith('bitten:'):
            # Ignore elements in foreign namespaces
            return None
        func_name = self._translate_name(elem.name)
        try:
            module = __import__(elem.namespace[7:], globals(), locals(),
                                [func_name])
            func = getattr(module, func_name)
            return func
        except (ImportError, AttributeError), e:
            raise InvalidRecipeError, 'Cannot load "%s" (%s)' % (elem.name, e)

    def _translate_name(self, name):
        name = name.replace('-', '_')
        if keyword.iskeyword(name) or name in __builtins__:
            name = name + '_'
        return name


class Recipe(object):
    """A build recipe.
    
    Iterate over this object to get the individual build steps in the order they
    have been defined in the recipe file.
    """

    ERROR = 'error'
    LOG = 'log'
    REPORT = 'report'

    def __init__(self, xml, basedir=os.getcwd()):
        assert isinstance(xml, xmlio.ParsedElement)
        self.ctxt = Context(basedir)
        self._root = xml
        self.description = self._root.attr.get('description')

    def __iter__(self):
        """Provide an iterator over the individual steps of the recipe."""
        for child in self._root.children('step'):
            yield Step(child)
