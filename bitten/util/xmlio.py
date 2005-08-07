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

def _escape_text(text):
    return str(text).replace('&', '&amp;').replace('<', '&lt;') \
                    .replace('>', '&gt;')

def _escape_attr(attr):
    return _escape_text(attr).replace('"', '&#34;')


class Fragment(object):
    """A collection of XML elements."""
    
    __slots__ = ['children']

    def __init__(self, *args, **attr):
        """Create an XML fragment."""
        self.children = []

    def __getitem__(self, nodes):
        """Add nodes to the fragment."""
        if not isinstance(nodes, (list, tuple)):
            nodes = [nodes]
        for node in nodes:
            self.append(node)
        return self

    def __str__(self):
        """Return a string representation of the XML fragment."""
        buf = StringIO()
        self.write(buf)
        return buf.getvalue()

    def append(self, node):
        """Append an element or fragment as child."""
        if isinstance(node, Element):
            self.children.append(node)
        elif isinstance(node, Fragment):
            self.children += node.children
        elif node is not None and node != '':
            self.children.append(node)

    def write(self, out, newlines=False):
        """Serializes the element and writes the XML to the given output
        stream.
        """
        for child in self.children:
            if isinstance(child, Element):
                child.write(out, newlines=newlines)
            else:
                if child[0] == '<':
                    out.write('<![CDATA[' + child + ']]>')
                else:
                    out.write(_escape_text(child))


class Element(Fragment):
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
    __slots__ = ['name', 'attr']

    def __init__(self, *args, **attr):
        """Create an XML element using the specified tag name.
        
        The tag name must be supplied as the first positional argument. All
        keyword arguments following it are handled as attributes of the element.
        """
        Fragment.__init__(self)
        self.name = args[0]
        self.attr = dict([(name, value) for name, value in attr.items()
                          if value is not None])

    def write(self, out, newlines=False):
        """Serializes the element and writes the XML to the given output
        stream.
        """
        out.write('<')
        out.write(self.name)
        for name, value in self.attr.items():
            out.write(' %s="%s"' % (name, _escape_attr(value)))
        if self.children:
            out.write('>')
            Fragment.write(self, out, newlines)
            out.write('</' + self.name + '>')
        else:
            out.write('/>')
        if newlines:
            out.write(os.linesep)


class SubElement(Element):

    __slots__ = []

    def __init__(self, parent, name, **attr):
        """Create an XML element using the specified tag name.
        
        The first positional argument is the instance of the parent element that
        this subelement should be appended to; the second positional argument is
        the name of the tag. All keyword arguments are handled as attributes of
        the element.
        """
        Element.__init__(self, name, **attr)
        parent.append(self)


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

    def write(self, out, newlines=False):
        """Serializes the element and writes the XML to the given output
        stream.
        """
        self._node.writexml(out, newl=newlines and '\n' or '')

    def __str__(self):
        """Return a string representation of the XML element."""
        buf = StringIO()
        self.write(buf)
        return buf.getvalue()


if __name__ == '__main__':
    import doctest
    doctest.testmod()
