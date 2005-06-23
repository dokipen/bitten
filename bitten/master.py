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
import os.path

from trac.env import Environment
from bitten import __version__ as VERSION
from bitten.model import Build, BuildConfig
from bitten.util import archive, beep, xmlio


class Master(beep.Listener):

    TRIGGER_INTERVAL = 10

    def __init__(self, env_path, ip, port):
        beep.Listener.__init__(self, ip, port)
        self.profiles[OrchestrationProfileHandler.URI] = OrchestrationProfileHandler

        self.env = Environment(env_path)
        self.slaves = {}
        self.schedule(self.TRIGGER_INTERVAL, self._check_build_triggers)
        self.build_queue = {}

    def _check_build_triggers(self, master, when):
        self.schedule(self.TRIGGER_INTERVAL, self._check_build_triggers)
        if not self.slaves:
            return

        logging.debug('Checking for build triggers...')
        repos = self.env.get_repository()
        try:
            repos.sync()

            for config in BuildConfig.select(self.env):
                node = repos.get_node(config.path)
                if (node.path, node.rev) in self.build_queue:
                    # Builds already pending
                    continue

                # Check whether the latest revision of that configuration has
                # already been built
                builds = list(Build.select(self.env, node.path, node.rev))
                if not builds:
                    logging.info('Enqueuing build of configuration "%s" as of revision [%s]',
                                 config.name, node.rev)
                    snapshot = archive.make_archive(self.env, repos, node.path,
                                                    node.rev, config.name)
                    logging.info('Created snapshot archive at %s' % snapshot)
                    self.build_queue[(node.path, node.rev)] = (config, snapshot)
        finally:
            repos.close()

        if self.build_queue:
            self.schedule(5, self._check_build_queue)

    def _check_build_queue(self, master, when):
        if self.build_queue:
            for path, rev in self.build_queue.keys():
                config, snapshot = self.build_queue[(path, rev)]
                logging.info('Building configuration "%s" as of revision [%s]',
                             config.name, rev)
                for slave in self.slaves.values():
                    if not slave.building:
                        slave.send_build(snapshot)
                        break


class OrchestrationProfileHandler(beep.ProfileHandler):
    """Handler for communication on the Bitten build orchestration profile from
    the perspective of the build master.
    """
    URI = 'http://bitten.cmlenz.net/beep/orchestration'

    def handle_connect(self, init_elem=None):
        self.master = self.session.listener
        assert self.master
        self.building = False
        self.slave_name = None

    def handle_disconnect(self):
        del self.master.slaves[self.slave_name]
        logging.info('Unregistered slave "%s"', self.slave_name)

    def handle_msg(self, msgno, msg):
        assert msg.get_content_type() == beep.BEEP_XML
        elem = xmlio.parse(msg.get_payload())

        if elem.tagname == 'register':
            platform, os, os_family, os_version = None, None, None, None
            for child in elem['*']:
                if child.tagname == 'platform':
                    platform = child.gettext()
                elif child.tagname == 'os':
                    os = child.gettext()
                    os_family = child.family
                    os_version = child.version

            self.slave_name = elem.name
            self.master.slaves[self.slave_name] = self

            xml = xmlio.Element('ok')
            self.channel.send_rpy(msgno, beep.MIMEMessage(xml))
            logging.info('Registered slave "%s" (%s running %s %s [%s])',
                         self.slave_name, platform, os, os_version, os_family)

    def send_build(self, archive_path, handle_reply=None):
        logging.info('Initiating build on slave %s', self.slave_name)
        self.building = True

        def handle_reply(cmd, msgno, msg):
            if cmd == 'ERR':
                if msg.get_content_type() == beep.BEEP_XML:
                    elem = xmlio.parse(msg.get_payload())
                    if elem.tagname == 'error':
                        logging.warning('Slave refused build request: %s (%d)',
                                        elem.gettext(), int(elem.code))
            logging.info('Build started')

        archive_name = os.path.basename(archive_path)
        message = beep.MIMEMessage(file(archive_path).read(),
                                   content_type='application/tar',
                                   content_disposition=archive_name,
                                   content_encoding='gzip')
        self.channel.send_msg(message, handle_reply=handle_reply)


def main():
    from optparse import OptionParser

    parser = OptionParser(usage='usage: %prog [options] env-path',
                          version='%%prog %s' % VERSION)
    parser.add_option('-p', '--port', action='store', type='int', dest='port',
                      help='port number to use')
    parser.add_option('-H', '--host', action='store', dest='host',
                      help='the host name or IP address to bind to')
    parser.add_option('--debug', action='store_const', dest='loglevel',
                      const=logging.DEBUG, help='enable debugging output')
    parser.add_option('-v', '--verbose', action='store_const', dest='loglevel',
                      const=logging.INFO, help='print as much as possible')
    parser.add_option('-q', '--quiet', action='store_const', dest='loglevel',
                      const=logging.ERROR, help='print as little as possible')
    parser.set_defaults(port=7633, loglevel=logging.WARNING)
    options, args = parser.parse_args()
    
    if len(args) < 1:
        parser.error('incorrect number of arguments')
    env_path = args[0]

    logging.getLogger().setLevel(options.loglevel)
    port = options.port
    if not (1 <= port <= 65535):
        parser.error('port must be an integer in the range 1-65535')

    host = options.host
    if not host:
        import socket
        ip = socket.gethostbyname(socket.gethostname())
        try:
            host = socket.gethostbyaddr(ip)[0]
        except socket.error, e:
            logging.warning('Reverse host name lookup failed (%s)', e)
            host = ip

    master = Master(env_path, host, port)
    try:
        master.run(timeout=5.0)
    except KeyboardInterrupt:
        master.quit()

if __name__ == '__main__':
    main()
