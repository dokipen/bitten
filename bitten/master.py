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
import logging
import os.path
import sys

from bitten.util import beep
from bitten.util.xmlio import Element, parse_xml


class BittenProfileHandler(beep.Profile):
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
            logging.info('Registered  slave %s (%s running %s %s [%s])',
                         elem.name, platform, os, os_version, os_family)


if __name__ == '__main__':
    options, args = getopt.getopt(sys.argv[1:], 'p:dvq',
                                  ['port=', 'debug', 'verbose', 'quiet'])
    if len(args) < 1:
        print>>sys.stderr, 'usage: %s [options] ENV_PATH' % os.path.basename(sys.argv[0])
        print>>sys.stderr
        print>>sys.stderr, 'Valid options:'
        print>>sys.stderr, '  -p [--port] arg\tport number to use (default: 7633)'
        print>>sys.stderr, '  -q [--quiet]\tprint as little as possible'
        print>>sys.stderr, '  -v [--verbose]\tprint as much as possible'
        sys.exit(2)

    port = 7633
    loglevel = logging.WARNING
    for opt, arg in options:
        if opt in ('-p', '--port'):
            try:
                port = int(arg)
            except ValueError:
                print>>sys.stderr, 'Port must be an integer'
        elif opt in ('-d', '--debug'):
            loglevel = logging.DEBUG
        elif opt in ('-v', '--verbose'):
            loglevel = logging.INFO
        elif opt in ('-q', '--quiet'):
            loglevel = logging.ERROR
    logging.getLogger().setLevel(loglevel)

    listener = beep.Listener('localhost', port)
    listener.profiles[BittenProfileHandler.URI] = BittenProfileHandler()
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass
