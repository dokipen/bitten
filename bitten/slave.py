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

from datetime import datetime
import logging
import os
import platform
import sys
import tempfile

from bitten.build import BuildError
from bitten.recipe import Recipe, InvalidRecipeError
from bitten.util import archive, beep, xmlio


class Slave(beep.Initiator):
    """Build slave."""

    def __init__(self, ip, port, name=None):
        beep.Initiator.__init__(self, ip, port)
        self.name = name

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

        def handle_reply(cmd, msgno, ansno, payload):
            if cmd == 'ERR':
                if payload.content_type == beep.BEEP_XML:
                    elem = xmlio.parse(payload.body)
                    if elem.name == 'error':
                        logging.error('Slave registration failed: %s (%d)',
                                      elem.gettext(), int(elem.attr['code']))
                raise beep.TerminateSession, 'Registration failed!'
            logging.info('Registration successful')

        system, node, release, version, machine, processor = platform.uname()
        system, release, version = platform.system_alias(system, release,
                                                         version)
        if self.session.name is not None:
            node = self.session.name
        logging.info('Registering with build master as %s', node)
        xml = xmlio.Element('register', name=node)[
            xmlio.Element('platform', processor=processor)[machine],
            xmlio.Element('os', family=os.name, version=release)[system]
        ]
        self.channel.send_msg(beep.Payload(xml), handle_reply)

    def handle_msg(self, msgno, payload):
        if payload.content_type == beep.BEEP_XML:
            elem = xmlio.parse(payload.body)
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
                self.channel.send_rpy(msgno, beep.Payload(xml))

        elif payload.content_type in ('application/tar', 'application/zip'):
            # Received snapshot archive for build
            workdir = tempfile.mkdtemp(prefix='bitten')

            archive_name = payload.content_disposition
            if not archive_name:
                if payload.content_type == 'application/tar':
                    if payload.content_encoding == 'gzip':
                        archive_name = 'snapshot.tar.gz'
                    elif payload.content_encoding == 'bzip2':
                        archive_name = 'snapshot.tar.bz2'
                    elif not payload.content_encoding:
                        archive_name = 'snapshot.tar'
                else:
                    archive_name = 'snapshot.zip'
            archive_path = os.path.join(workdir, archive_name)
            file(archive_path, 'wb').write(payload.body)
            logging.debug('Received snapshot archive: %s', archive_path)

            # Unpack the archive
            prefix = archive.unpack(archive_path, workdir)
            path = os.path.join(workdir, prefix)
            logging.debug('Unpacked snapshot to %s' % path)

            # Fix permissions
            for root, dirs, files in os.walk(workdir, topdown=False):
                for dirname in dirs:
                    os.chmod(os.path.join(root, dirname), 0700)
                for filename in files:
                    os.chmod(os.path.join(root, filename), 0400)

            self.execute_build(msgno, path, self.recipe_path)

    def execute_build(self, msgno, basedir, recipe_path):
        logging.info('Building in directory %s using recipe %s', basedir,
                     recipe_path)
        try:
            recipe = Recipe(recipe_path, basedir)

            xml = xmlio.Element('started', time=datetime.utcnow().isoformat())
            self.channel.send_ans(msgno, beep.Payload(xml))

            failed = False
            for step in recipe:
                logging.info('Executing build step "%s"', step.id)
                started = datetime.utcnow()
                try:
                    step.execute(recipe.ctxt)
                    duration = datetime.utcnow() - started
                    log = '\n'.join([record[-1] for record in recipe.ctxt._log])
                    xml = xmlio.Element('step', id=step.id, result='success',
                                        description=step.description,
                                        time=started.isoformat(),
                                        duration=duration.seconds)[log]
                    recipe.ctxt._log = []
                    self.channel.send_ans(msgno, beep.Payload(xml))
                except (BuildError, InvalidRecipeError), e:
                    duration = datetime.utcnow() - started
                    failed = True
                    xml = xmlio.Element('step', id=step.id, result='failure',
                                        description=step.description,
                                        time=started.isoformat(),
                                        duration=duration.seconds)[e]
                    self.channel.send_ans(msgno, beep.Payload(xml))

            logging.info('Build completed')
            recipe.ctxt._log = []
            xml = xmlio.Element('completed', time=datetime.utcnow().isoformat(),
                                result=['success', 'failure'][failed])
            self.channel.send_ans(msgno, beep.Payload(xml))

            self.channel.send_nul(msgno)

        except InvalidRecipeError, e:
            xml = xmlio.Element('error')[e]
            self.channel.send_ans(msgno, beep.Payload(xml))
            self.channel.send_nul(msgno)

        except (KeyboardInterrupt, SystemExit), e:
            xml = xmlio.Element('aborted')['Build cancelled']
            self.channel.send_ans(msgno, beep.Payload(xml))
            self.channel.send_nul(msgno)

            raise beep.TerminateSession, 'Cancelled'


def main():
    from bitten import __version__ as VERSION
    from optparse import OptionParser

    parser = OptionParser(usage='usage: %prog [options] host [port]',
                          version='%%prog %s' % VERSION)
    parser.add_option('-n', '--name', action='store', dest='name',
                      help='name of this slave (defaults to host name)')
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

    slave = Slave(host, port, options.name)
    try:
        slave.run()
    except KeyboardInterrupt:
        slave.quit()

if __name__ == '__main__':
    main()
