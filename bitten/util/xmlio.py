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

import os
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


__all__ = ['Element', 'parse']


class Element(object):
    """Simple XML output generator based on the builder pattern.

    Construct XML elements by passing the tag name to the constructor:

    >>> print Element('foo')
    <foo/>

    Attributes can be specified using keyword arguments. The values of the
    arguments will be converted to strings and any special XML characters
    escaped:

    >>> print Element('foo', bar=42)
    <foo bar="42"/>
    >>> print Element('foo', bar='1 < 2')
    <foo bar="1 &lt; 2"/>
    >>> print Element('foo', bar='"baz"')
    <foo bar="&#34;baz&#34;"/>

    The order in which attributes are rendered is undefined.

    Elements can be using item access notation:

    >>> print Element('foo')[Element('bar'), Element('baz')]
    <foo><bar/><baz/></foo>

    Text nodes can be nested in an element by using strings instead of elements
    in item access. Any special characters in the strings are escaped
    automatically:

    >>> print Element('foo')['Hello world']
    <foo>Hello world</foo>
    >>> print Element('foo')['1 < 2']
    <foo>1 &lt; 2</foo>

    This technique also allows mixed content:

    >>> print Element('foo')['Hello ', Element('b')['world']]
    <foo>Hello <b>world</b></foo>

    Finally, text starting with an opening angle bracket is treated specially:
    under the assumption that the text actually contains XML itself, the whole
    thing is wrapped in a CDATA block instead of escaping all special characters
    individually:

    >>> print Element('foo')['<bar a="3" b="4"><baz/></bar>']
    <foo><![CDATA[<bar a="3" b="4"><baz/></bar>]]></foo>
    """
    __slots__ = ['name', 'attr', 'children']

    def __init__(self, *args, **attr):
        """Create an XML element using the specified tag name.
        
        The tag name must be supplied as the first positional argument. All
        keyword arguments following it are handled as attributes of the element.
        """
        self.name = args[0]
        self.attr = dict([(name, value) for name, value in attr.items()
                          if value is not None])
        self.children = []

    def __getitem__(self, children):
        """Add child nodes to an element."""
        if not isinstance(children, (list, tuple)):
            children = [children]
        self.children = [child for child in children
                         if child is not None and child != '']
        return self

    def __str__(self):
        """Return a string representation of the XML element."""
        buf = StringIO()
        self.write(buf)
        return buf.getvalue()

    def write(self, out, newlines=False):
        """Serializes the element and writes the XML to the given output
        stream.
        """
        out.write('<')
        out.write(self.name)
        for name, value in self.attr.items():
            out.write(' %s="%s"' % (name, self._escape_attr(value)))
        if self.children:
            out.write('>')
            for child in self.children:
                if isinstance(child, Element):
                    child.write(out, newlines=newlines)
                else:
                    if child[0] == '<':
                        out.write('<![CDATA[' + child + ']]>')
                    else:
                        out.write(self._escape_text(child))
            out.write('</' + self.name + '>')
        else:
            out.write('/>')
        if newlines:
            out.write(os.linesep)

    def _escape_text(self, text):
        return str(text).replace('&', '&amp;').replace('<', '&lt;') \
                        .replace('>', '&gt;')

    def _escape_attr(self, attr):
        return self._escape_text(attr).replace('"', '&#34;')


class SubElement(Element):

    __slots__ = []

    def __init__(self, *args, **attr):
        """Create an XML element using the specified tag name.
        
        The first positional argument is the instance of the parent element that
        this subelement should be appended to; the second positional argument is
        the name of the tag. All keyword arguments are handled as attributes of
        the element.
        """
        assert len(args) == 2
        Element.__init__(self, args[1], **attr)
        args[0].children.append(self)


def parse(text):
    from xml.dom import minidom
    if isinstance(text, (str, unicode)):
        dom = minidom.parseString(text)
    else:
        dom = minidom.parse(text)
    return ParsedElement(dom.documentElement)


class ParsedElement(object):
    __slots__ = ['_node', 'attr']

    def __init__(self, node):
        self._node = node
        self.attr = dict([(name.encode(), value.encode()) for name, value
                          in node.attributes.items()])

    name = property(fget=lambda self: self._node.localName)
    namespace = property(fget=lambda self: self._node.namespaceURI)

    def children(self, name=None):
        for child in [c for c in self._node.childNodes if c.nodeType == 1]:
            if name in (None, child.tagName):
                yield ParsedElement(child)

    def __iter__(self):
        return self.children()

    def gettext(self):
        return ''.join([c.nodeValue for c in self._node.childNodes])


if __name__ == '__main__':
    import doctest
    doctest.testmod()
