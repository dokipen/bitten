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

import getopt
import logging
import os
import sys
import time

from bitten.util import beep
from bitten.util.xmlio import Element, parse_xml


class Slave(beep.Initiator):

    channelno = None # The channel number used by the bitten profile
    terminated = False

    def channel_started(self, channelno, profile_uri):
        if profile_uri == BittenProfileHandler.URI:
            self.channelno = channelno

    def greeting_received(self, profiles):
        if BittenProfileHandler.URI not in profiles:
            logging.error('Peer does not support Bitten profile')
            raise beep.TerminateSession, 'Peer does not support Bitten profile'
        self.channels[0].profile.send_start([BittenProfileHandler],
                                            handle_ok=self.channel_started)


class BittenProfileHandler(beep.ProfileHandler):
    """Handles communication on the Bitten profile from the client perspective.
    """
    URI = 'http://bitten.cmlenz.net/beep-profile/'

    def handle_connect(self):
        """Register with the build master."""
        sysname, nodename, release, version, machine = os.uname()
        logging.info('Registering with build master as %s', nodename)
        register = Element('register', name=nodename)[
            Element('platform')[machine],
            Element('os', family=os.name, version=release)[sysname]
        ]
        def handle_reply(cmd, msgno, msg):
            if cmd == 'ERR':
                if msg.get_content_type() == beep.BEEP_XML:
                    elem = parse_xml(msg.get_payload())
                    if elem.tagname == 'error':
                        raise beep.TerminateSession, \
                              '%s (%s)' % (elem.gettext(), elem.code)
                raise beep.TerminateSession, 'Registration failed!'
            logging.info('Registration successful')
        self.channel.send_msg(beep.MIMEMessage(register, beep.BEEP_XML),
                              handle_reply)

    def handle_msg(self, msgno, msg):
        # TODO: Handle build initiation requests
        pass


if __name__ == '__main__':
    options, args = getopt.getopt(sys.argv[1:], 'dvq',
                                  ['debug', 'verbose', 'quiet'])
    if len(args) < 1:
        print>>sys.stderr, 'Usage: %s [options] host [port]' % sys.argv[0]
        print>>sys.stderr
        print>>sys.stderr, 'Valid options:'
        print>>sys.stderr, '  -d [--debug]\tenable debugging output'
        print>>sys.stderr, '  -q [--quiet]\tprint as little as possible'
        print>>sys.stderr, '  -v [--verbose]\tprint as much as possible'
        sys.exit(2)

    host = args[0]
    if len(args) > 1:
        try:
            port = int(args[1])
        except ValueError:
            print>>sys.stderr, 'Port must be an integer'
            sys.exit(2)
    else:
        port = 7633

    loglevel = logging.WARNING
    for opt, arg in options:
        if opt in ('-d', '--debug'):
            loglevel = logging.DEBUG
        elif opt in ('-v', '--verbose'):
            loglevel = logging.INFO
        elif opt in ('-q', '--quiet'):
            loglevel = logging.ERROR
    logger = logging.getLogger()
    logger.setLevel(loglevel)

    slave = Slave(host, port)
    try:
        slave.run()
    except beep.TerminateSession, e:
        print>>sys.stderr, 'Session terminated:', e
