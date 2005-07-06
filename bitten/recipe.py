# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
#
# Bitten is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Trac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Christopher Lenz <cmlenz@gmx.de>

import logging
import os.path
import time

from bitten.build import BuildError
from bitten.util import xmlio

__all__ = ['Recipe']


class InvalidRecipeError(Exception):
    """Exception raised when a recipe cannot be processed."""


class Context(object):
    """The context in which a recipe command or report is run."""

    ERROR = 0
    OUTPUT = 1

    current_step = None
    current_function = None

    def __init__(self, basedir):
        self.basedir = basedir
        self._log = []

    def log(self, level, text):
        if text is None:
            return
        assert level in (Context.ERROR, Context.OUTPUT), \
               'Invalid log level %s' % level
        if level == Context.ERROR:
            logging.warning(text)
        else:
            logging.info(text)
        self._log.append((self.current_step, self.current_function, level,
                          time.time(), text))

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
            try:
                for function, args in self:
                    ctxt.current_function = function.__name__
                    function(ctxt, **args)
                    ctxt.current_function = None
            except BuildError, e:
                if self.onerror == 'fail':
                    raise BuildError, e
                logging.warning('Ignoring error in step %s (%s)', self.id, e)
                return None
        finally:
            ctxt.current_step = None

    def _args(self, elem):
        return dict([(name.replace('-', '_'), value) for name, value
                     in elem.attr.items()])

    def _function(self, elem):
        if not elem.namespace.startswith('bitten:'):
            # Ignore elements in foreign namespaces
            return None
        func_name = elem.name.replace('-', '_')
        try:
            module = __import__(elem.namespace[7:], globals(), locals(),
                                func_name)
            func = getattr(module, elem.name)
            return func
        except (ImportError, AttributeError), e:
            raise InvalidRecipeError, 'Cannot load "%s" (%s)' % (elem.name, e)


class Recipe(object):
    """A build recipe.
    
    Iterate over this object to get the individual build steps in the order they
    have been defined in the recipe file."""

    def __init__(self, filename='recipe.xml', basedir=os.getcwd()):
        self.ctxt = Context(basedir)
        fd = file(self.ctxt.resolve(filename), 'r')
        try:
            self._root = xmlio.parse(fd)
        finally:
            fd.close()
        self.description = self._root.attr.get('description')

    def __iter__(self):
        """Provide an iterator over the individual steps of the recipe."""
        for child in self._root.children('step'):
            yield Step(child)
