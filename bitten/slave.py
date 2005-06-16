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
import os
import sys
import time

from bitten.util import beep
from bitten.util.xmlio import Element, parse_xml


class Slave(beep.Initiator):

    channelno = None # The channel number used by the bitten profile

    def channel_started(self, channelno, profile_uri):
        if profile_uri == BittenProfileHandler.URI:
            self.channelno = channelno

    def greeting_received(self, profiles):
        if BittenProfileHandler.URI in profiles:
            self.channels[0].profile.send_start([BittenProfileHandler],
                                                handle_ok=self.channel_started)

class BittenProfileHandler(beep.Profile):
    """Handles communication on the Bitten profile from the client perspective.
    """
    URI = 'http://bitten.cmlenz.net/beep-profile/'

    def handle_connect(self):
        """Register with the build master."""
        sysname, nodename, release, version, machine = os.uname()
        print 'Registering with build master as %s' % nodename
        register = Element('register', name=nodename)[
            Element('platform')[machine],
            Element('os', family=os.name, version=release)[sysname]
        ]
        def handle_reply(cmd, msgno, msg):
            if cmd == 'RPY':
                print 'Registration successful'
            else:
                if msg.get_content_type() == beep.BEEP_XML:
                    elem = parse_xml(msg.get_payload())
                    if elem.tagname == 'error':
                        raise beep.TerminateSession, \
                              '%s (%s)' % (elem.gettext(), elem.code)
                raise beep.TerminateSession, 'Registration failed!'
        self.channel.send_msg(beep.MIMEMessage(register, beep.BEEP_XML),
                              handle_reply)

    def handle_msg(self, msgno, msg):
        # TODO: Handle build initiation requests
        pass


if __name__ == '__main__':
    options, args = getopt.getopt(sys.argv[1:], 'vq', ['verbose', 'qiuet'])
    if len(args) < 1:
        print>>sys.stderr, 'Usage: %s [options] host [port]' % sys.argv[0]
        print>>sys.stderr
        print>>sys.stderr, 'Valid options:'
        print>>sys.stderr, '  -q [--quiet]\tprint as little as possible'
        print>>sys.stderr, '  -v [--verbose]\tprint as much as possible'
        sys.exit(2)

    host = args[0]
    if len(args) > 1:
        port = int(args[1])
    else:
        port = 7633

    verbose = False
    quiet = False
    for opt, arg in options:
        if opt in ('-v', '--verbose'):
            verbose = True
        elif opt in ('-q', '--quiet'):
            quiet = True

    slave = Slave(host, port)
    try:
        try:
            asyncore.loop()
        except KeyboardInterrupt, beep.TerminateSession:
            def handle_ok():
                raise asyncore.ExitNow, 'Session terminated'
            def handle_error(code, message):
                print>>sys.stderr, \
                    'Build master refused to terminate session (%d): %s' \
                    % (code, message)
            slave.channels[0].profile.send_close(slave.channelno)
            slave.channels[0].profile.send_close(handle_ok=handle_ok,
                                                 handle_error=handle_error)
            time.sleep(.25)
    except beep.TerminateSession, e:
        print e
