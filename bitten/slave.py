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
import tempfile
import time

from bitten import __version__ as VERSION
from bitten.util import beep, xmlio


class Slave(beep.Initiator):

    def greeting_received(self, profiles):
        if OrchestrationProfileHandler.URI not in profiles:
            err = 'Peer does not support the Bitten orchestration profile'
            logging.error(err)
            raise beep.TerminateSession, err
        self.channels[0].profile.send_start([OrchestrationProfileHandler])


class OrchestrationProfileHandler(beep.ProfileHandler):
    """Handler for communication on the Bitten build orchestration profile from
    the perspective of the build slave.
    """
    URI = 'http://bitten.cmlenz.net/beep/orchestration'

    def handle_connect(self, init_elem=None):
        """Register with the build master."""
        def handle_reply(cmd, msgno, msg):
            if cmd == 'ERR':
                if msg.get_content_type() == beep.BEEP_XML:
                    elem = xmlio.parse(msg.get_payload())
                    if elem.tagname == 'error':
                        raise beep.TerminateSession, \
                              '%s (%d)' % (elem.gettext(), int(elem.code))
                raise beep.TerminateSession, 'Registration failed!'
            logging.info('Registration successful')

        sysname, nodename, release, version, machine = os.uname()
        logging.info('Registering with build master as %s', nodename)
        xml = xmlio.Element('register', name=nodename)[
            xmlio.Element('platform')[machine],
            xmlio.Element('os', family=os.name, version=release)[sysname]
        ]
        self.channel.send_msg(beep.MIMEMessage(xml), handle_reply)

    def handle_msg(self, msgno, msg):
        if msg.get_content_type() == 'application/tar':
            workdir = tempfile.mkdtemp(prefix='bitten')
            archive_name = msg.get('Content-Disposition', 'snapshot.tar.gz')
            archive_path = os.path.join(workdir, archive_name)
            file(archive_path, 'wb').write(msg.get_payload())
            logging.info('Received snapshot archive: %s', archive_path)

            # TODO: Spawn the build process

            xml = xmlio.Element('ok')
            self.channel.send_rpy(msgno, beep.MIMEMessage(xml))

        else:
            xml = xmlio.Element('error', code=500)['Sorry, what?']
            self.channel.send_err(msgno, beep.MIMEMessage(xml))


def main():
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
        except (AssertionError, ValueError):
            parser.error('port must be an integer in the range 1-65535')
    else:
        port = 7633

    logging.getLogger().setLevel(options.loglevel)

    slave = Slave(host, port)
    try:
        slave.run()
    except KeyboardInterrupt:
        slave.quit()

if __name__ == '__main__':
    main()
