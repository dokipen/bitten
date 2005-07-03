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
import time

from trac.env import Environment
from bitten.model import Build, BuildConfig, TargetPlatform
from bitten.util import archive, beep, xmlio


class Master(beep.Listener):

    TRIGGER_INTERVAL = 10

    def __init__(self, env_path, ip, port):
        beep.Listener.__init__(self, ip, port)
        self.profiles[OrchestrationProfileHandler.URI] = OrchestrationProfileHandler
        self.env = Environment(env_path)

        self.slaves = {}

        # path to generated snapshot archives, key is (config name, revision)
        self.snapshots = {}

        self.schedule(self.TRIGGER_INTERVAL, self._check_build_triggers)

    def close(self):
        # Remove all pending builds
        for build in Build.select(self.env, status=Build.PENDING):
            build.delete()
        beep.Listener.close(self)

    def _check_build_triggers(self, master, when):
        self.schedule(self.TRIGGER_INTERVAL, self._check_build_triggers)

        logging.debug('Checking for build triggers...')
        repos = self.env.get_repository()
        try:
            repos.sync()

            for config in BuildConfig.select(self.env):
                node = repos.get_node(config.path)
                for path, rev, chg in node.get_history():
                    # Check whether the latest revision of that configuration
                    # has already been built
                    builds = Build.select(self.env, config.name, rev)
                    if not list(builds):
                        logging.info('Enqueuing build of configuration "%s" as '
                                     'of revision [%s]', config.name, rev)
                        build = Build(self.env)
                        build.config = config.name
                        build.rev = rev
                        build.rev_time = repos.get_changeset(rev).date
                        build.insert()
                        break
        finally:
            repos.close()

        self.schedule(5, self._check_build_queue)

    def _check_build_queue(self, master, when):
        if not self.slaves:
            return
        logging.debug('Checking for pending builds...')
        for build in Build.select(self.env, status=Build.PENDING):
            for slave in self.slaves.values():
                active_builds = Build.select(self.env, slave=slave.name,
                                             status=Build.IN_PROGRESS)
                if not list(active_builds):
                    slave.send_initiation(build)
                    return

    def get_snapshot(self, build, type, encoding):
        formats = {
            ('application/tar', 'bzip2'): 'bzip2',
            ('application/tar', 'gzip'): 'bzip',
            ('application/tar', None): 'tar',
            ('application/zip', None): 'zip',
        }
        if not (build.config, build.rev, type, encoding) in self.snapshots:
            config = BuildConfig(self.env, build.config)
            snapshot = archive.pack(self.env, path=config.path, rev=build.rev,
                                    prefix=config.name,
                                    format=formats[(type, encoding)])
            logging.info('Prepared snapshot archive at %s' % snapshot)
            self.snapshots[(build.config, build.rev, type, encoding)] = snapshot
        return self.snapshots[(build.config, build.rev, type, encoding)]


class OrchestrationProfileHandler(beep.ProfileHandler):
    """Handler for communication on the Bitten build orchestration profile from
    the perspective of the build master.
    """
    URI = 'http://bitten.cmlenz.net/beep/orchestration'

    def handle_connect(self):
        self.master = self.session.listener
        assert self.master
        self.env = self.master.env
        assert self.env
        self.name = None
        self.props = {}

    def handle_disconnect(self):
        if self.name is None:
            # Slave didn't successfully register before disconnecting, so
            # there's nothing to clean up
            return

        del self.master.slaves[self.name]

        for build in Build.select(self.env, slave=self.name,
                                  status=Build.IN_PROGRESS):
            logging.info('Build [%s] of "%s" by %s cancelled', build.rev,
                         build.config, self.name)
            build.slave = None
            build.status = Build.PENDING
            build.started = 0
            build.update()
            break
        logging.info('Unregistered slave "%s"', self.name)

    def handle_msg(self, msgno, msg):
        assert msg.get_content_type() == beep.BEEP_XML
        elem = xmlio.parse(msg.get_payload())

        if elem.name == 'register':
            self.name = elem.attr['name']
            for child in elem.children():
                if child.name == 'platform':
                    self.props[Build.MACHINE] = child.gettext()
                    self.props[Build.PROCESSOR] = child.attr.get('processor')
                elif child.name == 'os':
                    self.props[Build.OS_NAME] = child.gettext()
                    self.props[Build.OS_FAMILY] = child.attr.get('family')
                    self.props[Build.OS_VERSION] = child.attr.get('version')
            self.props[Build.IP_ADDRESS] = self.session.addr[0]

            self.name = elem.attr['name']
            self.master.slaves[self.name] = self

            xml = xmlio.Element('ok')
            self.channel.send_rpy(msgno, beep.MIMEMessage(xml))
            logging.info('Registered slave "%s"', self.name)

    def send_initiation(self, build):
        logging.debug('Initiating build of "%s" on slave %s', build.config,
                      self.name)

        def handle_reply(cmd, msgno, ansno, msg):
            if cmd == 'ERR':
                if msg.get_content_type() == beep.BEEP_XML:
                    elem = xmlio.parse(msg.get_payload())
                    if elem.name == 'error':
                        logging.warning('Slave refused build request: %s (%d)',
                                        elem.gettext(), int(elem.attr['code']))
                return

            elem = xmlio.parse(msg.get_payload())
            assert elem.name == 'proceed'
            type = encoding = None
            for child in elem.children('accept'):
                type, encoding = child.attr['type'], child.attr.get('encoding')
                if (type, encoding) in (('application/tar', 'gzip'),
                                        ('application/tar', 'bzip2'),
                                        ('application/tar', None),
                                        ('application/zip', None)):
                    break
                type = None
            if not type:
                xml = xmlio.Element('error', code=550)[
                    'None of the accepted archive formats supported'
                ]
                self.channel.send_err(beep.MIMEMessage(xml))
                return
            self.send_snapshot(build, type, encoding)

        xml = xmlio.Element('build', recipe='recipe.xml')
        self.channel.send_msg(beep.MIMEMessage(xml), handle_reply=handle_reply)

    def send_snapshot(self, build, type, encoding):

        def handle_reply(cmd, msgno, ansno, msg):
            if cmd == 'ERR':
                assert msg.get_content_type() == beep.BEEP_XML
                elem = xmlio.parse(msg.get_payload())
                if elem.name == 'error':
                    logging.warning('Slave did not accept archive: %s (%d)',
                                    elem.gettext(), int(elem.attr['code']))
            if cmd == 'ANS':
                elem = xmlio.parse(msg.get_payload())
                logging.debug('Received build answer <%s>' % elem.name)
                if elem.name == 'started':
                    self.steps = []
                    build.slave = self.name
                    build.slave_info = self.props
                    build.started = int(time.time())
                    build.status = Build.IN_PROGRESS
                    build.update()
                    logging.info('Slave %s started build of "%s" as of [%s]',
                                 self.name, build.config, build.rev)
                elif elem.name == 'step':
                    logging.info('Slave completed step "%s"',
                                 elem.attr['id'])
                    if elem.attr['result'] == 'failure':
                        logging.warning('Step failed: %s', elem.gettext())
                    self.steps.append((elem.attr['id'],
                                       elem.attr['result']))
                elif elem.name == 'aborted':
                    logging.info('Slave "%s" aborted build', self.name)
                    build.slave = None
                    build.started = 0
                    build.status = Build.PENDING
                elif elem.name == 'error':
                    build.status = Build.FAILURE
            elif cmd == 'NUL':
                if build.status != Build.PENDING: # Completed
                    logging.info('Slave %s completed build of "%s" as of [%s]',
                                 self.name, build.config, build.rev)
                    build.stopped = int(time.time())
                    if build.status is Build.IN_PROGRESS:
                        # Find out whether the build failed or succeeded
                        if [st for st in self.steps if st[1] == 'failure']:
                            build.status = Build.FAILURE
                        else:
                            build.status = Build.SUCCESS
                else: # Aborted
                    build.slave = None
                    build.started = 0
                build.update()

        # TODO: should not block while reading the file; rather stream it using
        #       asyncore push_with_producer()
        snapshot_path = self.master.get_snapshot(build, type, encoding)
        snapshot_name = os.path.basename(snapshot_path)
        message = beep.MIMEMessage(file(snapshot_path).read(),
                                   content_disposition=snapshot_name,
                                   content_type=type, content_encoding=encoding)
        self.channel.send_msg(message, handle_reply=handle_reply)


def main():
    from bitten import __version__ as VERSION
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
