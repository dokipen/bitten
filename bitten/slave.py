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
from bitten.util import archive, beep, xmlio


class Slave(beep.Initiator):
    """Build slave."""

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

    def handle_connect(self):
        """Register with the build master."""
        self.recipe_path = None

        def handle_reply(cmd, msgno, msg):
            if cmd == 'ERR':
                if msg.get_content_type() == beep.BEEP_XML:
                    elem = xmlio.parse(msg.get_payload())
                    if elem.name == 'error':
                        raise beep.TerminateSession, '%s (%d)' \
                            % (elem.gettext(), int(elem.attr['code']))
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
        content_type = msg.get_content_type()
        if content_type == beep.BEEP_XML:
            elem = xmlio.parse(msg.get_payload())
            if elem.name == 'build':
                # Received a build request
                self.recipe_path = elem.attr['recipe']

                xml = xmlio.Element('proceed')[
                    xmlio.Element('accept', type='application/tar',
                                  encoding='bzip2'),
                    xmlio.Element('accept', type='application/tar',
                                  encoding='gzip'),
                    xmlio.Element('accept', type='application/zip')
                ]
                self.channel.send_rpy(msgno, beep.MIMEMessage(xml))

        elif content_type in ('application/tar', 'application/zip'):
            # Received snapshot archive for build
            workdir = tempfile.mkdtemp(prefix='bitten')

            archive_name = msg.get('Content-Disposition')
            if not archive_name:
                if content_type == 'application/tar':
                    encoding = msg.get('Content-Transfer-Encoding')
                    if encoding == 'gzip':
                        archive_name = 'snapshot.tar.gz'
                    elif encoding == 'bzip2':
                        archive_name = 'snapshot.tar.bz2'
                    elif not encoding:
                        archive_name = 'snapshot.tar'
                else:
                    archive_name = 'snapshot.zip'
            archive_path = os.path.join(workdir, archive_name)
            file(archive_path, 'wb').write(msg.get_payload())
            logging.debug('Received snapshot archive: %s', archive_path)

            # Unpack the archive
            prefix = archive.unpack(archive_path, workdir)
            path = os.path.join(workdir, prefix)
            logging.info('Unpacked snapshot to %s' % path)

            # Fix permissions
            for root, dirs, files in os.walk(workdir, topdown=False):
                for dirname in dirs:
                    os.chmod(os.path.join(root, dirname), 0700)
                for filename in files:
                    os.chmod(os.path.join(root, filename), 0400)

            xml = xmlio.Element('ok')
            self.channel.send_rpy(msgno, beep.MIMEMessage(xml))

            self.execute_build(path, self.recipe_path)

    def execute_build(self, basedir, recipe):
        logging.info('Would now build in directory %s using recipe %s',
                     basedir, recipe)
        # TODO: Start the build process


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
