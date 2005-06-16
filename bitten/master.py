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

import asyncore
import getopt
import os.path
import sys

from bitten.util import beep
from bitten.util.xmlio import Element, parse_xml


class BittenProfile(beep.Profile):
    URI = 'http://bitten.cmlenz.net/beep-profile/'

    def __init__(self):
        beep.Profile.__init__(self)

    def handle_msg(self, msgno, msg):
        assert msg.get_content_type() == beep.BEEP_XML
        elem = parse_xml(msg.get_payload())

        if elem.tagname == 'register':
            platform, os, os_family, os_version = None, None, None, None
            for child in elem['*']:
                if child.tagname == 'platform':
                    platform = child.gettext()
                elif child.tagname == 'os':
                    os = child.gettext()
                    os_family = child.family
                    os_version = child.version
            rpy = beep.MIMEMessage(Element('ok'), beep.BEEP_XML)
            self.channel.send_rpy(msgno, rpy)
            print 'Connected to %s (%s running %s %s [%s])' \
                  % (elem.name, platform, os, os_version, os_family)


if __name__ == '__main__':
    options, args = getopt.getopt(sys.argv[1:], 'p:', ['port='])
    if len(args) < 1:
        print>>sys.stderr, 'usage: %s [options] ENV_PATH' % os.path.basename(sys.argv[0])
        print>>sys.stderr
        print>>sys.stderr, 'Valid options:'
        print>>sys.stderr, '  -p [--port] arg\tport number to use (default: 7633)'
        sys.exit(2)

    if len(args) > 1:
        port = int(args[1])
    else:
        port = 7633

    listener = beep.Listener('localhost', port)
    listener.profiles[BittenProfile.URI] = BittenProfile()
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass
