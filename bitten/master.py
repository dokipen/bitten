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

from itertools import ifilter
import logging
import os.path
import re
try:
    set
except NameError:
    from sets import Set as set
import time

from trac.env import Environment
from bitten.model import BuildConfig, TargetPlatform, Build, BuildStep
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

        repos = self.env.get_repository()
        try:
            repos.sync()

            for config in BuildConfig.select(self.env):
                logging.debug('Checking for changes to "%s" at %s',
                              config.label, config.path)
                node = repos.get_node(config.path)
                for path, rev, chg in node.get_history():
                    enqueued = False
                    for platform in TargetPlatform.select(self.env, config.name):
                        # Check whether the latest revision of the configuration
                        # has already been built on this platform
                        builds = Build.select(self.env, config.name, rev,
                                              platform.id)
                        if not list(builds):
                            logging.info('Enqueuing build of configuration "%s"'
                                         ' at revision [%s] on %s', config.name,
                                         rev, platform.name)
                            build = Build(self.env)
                            build.config = config.name
                            build.rev = rev
                            build.rev_time = repos.get_changeset(rev).date
                            build.platform = platform.id
                            build.insert()
                            enqueued = True
                    if enqueued:
                        break
        finally:
            repos.close()

        self.schedule(5, self._check_build_queue)

    def _check_build_queue(self, master, when):
        if not self.slaves:
            return
        logging.debug('Checking for pending builds...')
        for build in Build.select(self.env, status=Build.PENDING):
            for slave in self.slaves[build.platform]:
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

    def register(self, handler):
        any_match = False
        for config in BuildConfig.select(self.env):
            for platform in TargetPlatform.select(self.env, config=config.name):
                if not platform.id in self.slaves:
                    self.slaves[platform.id] = set()
                logging.debug('Matching slave %s against rules: %s',
                              handler.name, platform.rules)
                match = True
                for property, pattern in ifilter(None, platform.rules):
                    try:
                        if not re.match(pattern, handler.info.get(property)):
                            match = any_match = False
                            break
                    except re.error, e:
                        logging.error('Invalid platform matching pattern "%s"',
                                      pattern, exc_info=True)
                        match = False
                        break
                if match:
                    self.slaves[platform.id].add(handler)

        if not any_match:
            logging.warning('Slave %s does not match any of the configured '
                            'target platforms', handler.name)
            return False

        logging.info('Registered slave "%s"', handler.name)
        return True

    def unregister(self, handler):
        for slaves in self.slaves.values():
            slaves.discard(handler)

        for build in Build.select(self.env, slave=handler.name,
                                  status=Build.IN_PROGRESS):
            logging.info('Build [%s] of "%s" by %s cancelled', build.rev,
                         build.config, handler.name)
            build.slave = None
            build.status = Build.PENDING
            build.started = 0
            build.update()
            break
        logging.info('Unregistered slave "%s"', handler.name)


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
        self.info = {}

    def handle_disconnect(self):
        self.master.unregister(self)

    def handle_msg(self, msgno, msg):
        assert msg.get_content_type() == beep.BEEP_XML
        elem = xmlio.parse(msg.get_payload())

        if elem.name == 'register':
            self.name = elem.attr['name']
            for child in elem.children():
                if child.name == 'platform':
                    self.info[Build.MACHINE] = child.gettext()
                    self.info[Build.PROCESSOR] = child.attr.get('processor')
                elif child.name == 'os':
                    self.info[Build.OS_NAME] = child.gettext()
                    self.info[Build.OS_FAMILY] = child.attr.get('family')
                    self.info[Build.OS_VERSION] = child.attr.get('version')
            self.info[Build.IP_ADDRESS] = self.session.addr[0]

            if not self.master.register(self):
                xml = xmlio.Element('error', code=550)[
                    'Nothing for you to build here, please move along'
                ]
                self.channel.send_err(msgno, beep.MIMEMessage(xml))
                return

            xml = xmlio.Element('ok')
            self.channel.send_rpy(msgno, beep.MIMEMessage(xml))

    def send_initiation(self, build):
        logging.debug('Initiating build of "%s" on slave %s', build.config,
                      self.name)

        def handle_reply(cmd, msgno, ansno, msg):
            if cmd == 'ERR':
                if msg.get_content_type() == beep.BEEP_XML:
                    elem = xmlio.parse(msg.get_payload())
                    if elem.name == 'error':
                        logging.warning('Slave %s refused build request: '
                                        '%s (%d)', self.name, elem.gettext(),
                                        int(elem.attr['code']))
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
                    logging.warning('Slave %s did not accept archive: %s (%d)',
                                    self.name, elem.gettext(),
                                    int(elem.attr['code']))

            if cmd == 'ANS':
                elem = xmlio.parse(msg.get_payload())

                if elem.name == 'started':
                    build.slave = self.name
                    build.slave_info.update(self.info)
                    build.started = int(_parse_iso_datetime(elem.attr['time']))
                    build.status = Build.IN_PROGRESS
                    build.update()
                    logging.info('Slave %s started build of "%s" as of [%s]',
                                 self.name, build.config, build.rev)

                elif elem.name == 'step':
                    logging.info('Slave completed step "%s"', elem.attr['id'])
                    step = BuildStep(self.env)
                    step.build = build.id
                    step.name = elem.attr['id']
                    step.description = elem.attr.get('description')
                    step.started = int(_parse_iso_datetime(elem.attr['time']))
                    step.stopped = step.started + int(elem.attr['duration'])
                    step.log = elem.gettext().strip()
                    if elem.attr['result'] == 'failure':
                        logging.warning('Step failed: %s', elem.gettext())
                        step.status = BuildStep.FAILURE
                    else:
                        step.status = BuildStep.SUCCESS
                    step.insert()

                elif elem.name == 'completed':
                    logging.info('Slave %s completed build of "%s" as of [%s]',
                                 self.name, build.config, build.rev)
                    build.stopped = int(_parse_iso_datetime(elem.attr['time']))
                    if elem.attr['result'] == 'failure':
                        build.status = Build.FAILURE
                    else:
                        build.status = Build.SUCCESS

                elif elem.name == 'aborted':
                    logging.info('Slave "%s" aborted build', self.name)
                    build.slave = None
                    build.started = 0
                    build.status = Build.PENDING

                elif elem.name == 'error':
                    build.status = Build.FAILURE

                build.update()

        # TODO: should not block while reading the file; rather stream it using
        #       asyncore push_with_producer()
        snapshot_path = self.master.get_snapshot(build, type, encoding)
        snapshot_name = os.path.basename(snapshot_path)
        message = beep.MIMEMessage(file(snapshot_path).read(),
                                   content_disposition=snapshot_name,
                                   content_type=type, content_encoding=encoding)
        self.channel.send_msg(message, handle_reply=handle_reply)


def _parse_iso_datetime(string):
    """Minimal parser for ISO date-time strings.
    
    Return the time as floating point number. Only handles UTC timestamps
    without time zone information."""
    try:
        string = string.split('.', 1)[0] # strip out microseconds
        secs = time.mktime(time.strptime(string, '%Y-%m-%dT%H:%M:%S'))
        tzoffset = time.timezone
        if time.daylight:
            tzoffset = time.altzone
        return secs - tzoffset
    except ValueError, e:
        raise ValueError, 'Invalid ISO date/time %s (%s)' % (string, e)


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
