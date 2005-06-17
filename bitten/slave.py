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
import os
import sys
import time

from bitten import __version__ as VERSION
from bitten.util import beep
from bitten.util.xmlio import Element, parse_xml


class Slave(beep.Initiator):

    channelno = None # The channel number used by the bitten profile
    terminated = False

    def channel_started(self, channelno, profile_uri):
        if profile_uri == OrchestrationProfileHandler.URI:
            self.channelno = channelno

    def greeting_received(self, profiles):
        if OrchestrationProfileHandler.URI not in profiles:
            logging.error('Peer does not support Bitten profile')
            raise beep.TerminateSession, 'Peer does not support Bitten profile'
        self.channels[0].profile.send_start([OrchestrationProfileHandler],
                                            handle_ok=self.channel_started)


class OrchestrationProfileHandler(beep.ProfileHandler):
    """Handler for communication on the Bitten build orchestration profile from
    the perspective of the build slave.
    """
    URI = 'http://bitten.cmlenz.net/beep/orchestration'

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
        # TODO: Handle build initiation requests etc
        pass


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage='usage: %prog [options] host [port]',
                          version='%%prog %s' % VERSION)
    parser.add_option('--debug', action='store_const', dest='loglevel',
                      const=logging.DEBUG, help='enable debugging output')
    parser.add_option('-v', '--verbose', action='store_const', dest='loglevel',
                      const=logging.INFO, help='print as much as possible')
    parser.add_option('-q', '--quiet', action='store_const', dest='loglevel',
                      const=logging.ERROR, help='print as little as possible')
    parser.set_defaults(loglevel=logging.WARNING)
    options, args = parser.parse_args()

    if len(args) < 1:
        parser.error('incorrect number of arguments')
    host = args[0]
    if len(args) > 1:
        try:
            port = int(args[1])
            assert (1 <= port <= 65535), 'port number out of range'
        except AssertionError, ValueError:
            parser.error('port must be an integer in the range 1-65535')
    else:
        port = 7633

    logging.getLogger().setLevel(options.loglevel)

    slave = Slave(host, port)
    slave.run()
