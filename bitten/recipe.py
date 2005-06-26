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

import os.path

from bitten import BuildError
from bitten.util import xmlio

__all__ = ['Recipe']


class Step(object):
    """Represents a single step of a build recipe.

    Iterate over an object of this class to get the commands to execute, and
    their keyword arguments.
    """

    def __init__(self, elem):
        self._elem = elem
        self.id = elem.id
        self.description = elem.description

    def __iter__(self):
        for child in self._elem:
            if child.namespace:
                # Commands
                yield self._translate(child), child.attrs
            elif child.name == 'reports':
                # Reports
                for grandchild in child:
                    yield self._translate(grandchild), grandchild.attrs
            else:
                raise BuildError, "Unknown element <%s>" % child.name

    def _translate(self, elem):
        if not elem.namespace.startswith('bitten:'):
            # Ignore elements in foreign namespaces
            return None

        module = __import__(elem.namespace[7:], globals(), locals(), elem.name)
        func = getattr(module, elem.name)
        return func


class Recipe(object):
    """Represents a build recipe.
    
    Iterate over this object to get the individual build steps in the order they
    have been defined in the recipe file."""

    def __init__(self, filename='recipe.xml', basedir=os.getcwd()):
        self.filename = filename
        self.basedir = basedir
        self.path = os.path.join(basedir, filename)
        self.root = xmlio.parse(file(self.path, 'r'))
        assert self.root.name == 'build'
        self.description = self.root.attr['description']

    def __iter__(self):
        """Provide an iterator over the individual steps of the recipe."""
        for child in self.root.children('step'):
            yield Step(child)
