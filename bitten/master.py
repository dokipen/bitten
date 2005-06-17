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

from trac.env import Environment
from bitten import __version__ as VERSION
from bitten.util import beep
from bitten.util.xmlio import Element, parse_xml


class Master(beep.Listener):

    TRIGGER_INTERVAL = 10

    def __init__(self, env_path, ip, port):
        beep.Listener.__init__(self, ip, port)
        self.profiles[OrchestrationProfileHandler.URI] = OrchestrationProfileHandler

        self.env = Environment(env_path)
        self.youngest_rev = None
        self.slaves = {}
        self.schedule(self.TRIGGER_INTERVAL, self.check_trigger)

    def check_trigger(self, master, when):
        logging.debug('Checking for build triggers...')
        repos = self.env.get_repository()
        repos.sync()
        if repos.youngest_rev != self.youngest_rev:
            logging.info('New changeset detected: [%s]'
                          % repos.youngest_rev)
            self.youngest_rev = repos.youngest_rev
        repos.close()
        self.schedule(self.TRIGGER_INTERVAL, self.check_trigger)


class OrchestrationProfileHandler(beep.ProfileHandler):
    """Handler for communication on the Bitten build orchestration profile from
    the perspective of the build master.
    """
    URI = 'http://bitten.cmlenz.net/beep/orchestration'

    def handle_connect(self):
        self.master = self.session.listener
        assert self.master
        self.slave_name = None

    def handle_disconnect(self):
        del self.master.slaves[self.slave_name]
        logging.info('Unregistered slave "%s"', self.slave_name)

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

            self.slave_name = elem.name
            self.master.slaves[self.slave_name] = self

            rpy = beep.MIMEMessage(Element('ok'), beep.BEEP_XML)
            self.channel.send_rpy(msgno, rpy)
            logging.info('Registered slave "%s" (%s running %s %s [%s])',
                         self.slave_name, platform, os, os_version, os_family)


if __name__ == '__main__':
    from optparse import OptionParser

    parser = OptionParser(usage='usage: %prog [options] env-path',
                          version='%%prog %s' % VERSION)
    parser.add_option('-p', '--port', action='store', type='int', dest='port',
                      help='port number to use')
    parser.add_option('-H', '--host', action='store', dest='host',
                      help='the host name of IP address to bind to')
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
        master.run()
    except KeyboardInterrupt:
        pass
