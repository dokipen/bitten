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
from xml.dom import minidom

from bitten import BuildError

__all__ = ['Recipe']


class Step(object):
    """Represents a single step of a build recipe.

    Iterate over an object of this class to get the commands to execute, and
    their keyword arguments.
    """

    def __init__(self, node):
        self._node = node
        self.id = node.getAttribute('id')
        self.description = node.getAttribute('description')

    def __iter__(self):
        for child in [c for c in self._node.childNodes if c.nodeType == 1]:
            if child.namespaceURI:
                # Commands
                yield self._translate(child)
            elif child.tagName == 'reports':
                # Reports
                for child in [c for c in child.childNodes if c.nodeType == 1]:
                    yield self._translate(child)
            else:
                raise BuildError, "Unknown element <%s>" % child.tagName

    def _translate(self, node):
        if not node.namespaceURI.startswith('bitten:'):
            # Ignore elements in a foreign namespace
            return None

        module = __import__(node.namespaceURI[7:], globals(), locals(),
                            node.localName)
        func = getattr(module, node.localName)
        attrs = {}
        for name, value in node.attributes.items():
            attrs[name.encode()] = value.encode()
        return func, attrs


class Recipe(object):
    """Represents a build recipe.
    
    Iterate over this object to get the individual build steps in the order they
    have been defined in the recipe file."""

    def __init__(self, filename='recipe.xml', basedir=os.getcwd()):
        self.filename = filename
        self.basedir = basedir
        self.path = os.path.join(basedir, filename)
        self.root = minidom.parse(self.path).documentElement
        self.description = self.root.getAttribute('description')

    def __iter__(self):
        """Provide an iterator over the individual steps of the recipe."""
        for child in self.root.getElementsByTagName('step'):
            yield Step(child)
