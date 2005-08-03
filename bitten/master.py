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

from datetime import datetime, timedelta
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

log = logging.getLogger('bitten.master')

DEFAULT_CHECK_INTERVAL = 120 # 2 minutes


class Master(beep.Listener):

    def __init__(self, env_path, ip, port,
                 check_interval=DEFAULT_CHECK_INTERVAL):
        beep.Listener.__init__(self, ip, port)
        self.profiles[OrchestrationProfileHandler.URI] = OrchestrationProfileHandler
        self.env = Environment(env_path)
        self.check_interval = check_interval

        self.slaves = {}

        # path to generated snapshot archives, key is (config name, revision)
        self.snapshots = {}
        for config in BuildConfig.select(self.env):
            snapshots = archive.index(self.env, prefix=config.name)
            for rev, format, path in snapshots:
                self.snapshots[(config.name, rev, format)] = path

        self._cleanup_orphaned_builds()
        self.schedule(self.check_interval, self._check_build_triggers)

    def close(self):
        self._cleanup_orphaned_builds()
        beep.Listener.close(self)

    def _check_build_triggers(self, when):
        self.schedule(self.check_interval, self._check_build_triggers)

        repos = self.env.get_repository()
        try:
            repos.sync()

            for config in BuildConfig.select(self.env):
                log.debug('Checking for changes to "%s" at %s', config.label,
                          config.path)
                node = repos.get_node(config.path)
                for path, rev, chg in node.get_history():
                    enqueued = False
                    for platform in TargetPlatform.select(self.env, config.name):
                        # Check whether the latest revision of the configuration
                        # has already been built on this platform
                        builds = Build.select(self.env, config.name, rev,
                                              platform.id)
                        if not list(builds):
                            log.info('Enqueuing build of configuration "%s" at '
                                     'revision [%s] on %s', config.name, rev,
                                     platform.name)
                            build = Build(self.env)
                            build.config = config.name
                            build.rev = str(rev)
                            build.rev_time = repos.get_changeset(rev).date
                            build.platform = platform.id
                            build.insert()
                            enqueued = True
                    if enqueued:
                        break
        finally:
            repos.close()

        self.schedule(self.check_interval * 0.2, self._check_build_queue)
        self.schedule(self.check_interval * 1.8, self._cleanup_snapshots)

    def _check_build_queue(self, when):
        if not self.slaves:
            return
        log.debug('Checking for pending builds...')
        for build in Build.select(self.env, status=Build.PENDING):
            for slave in self.slaves.get(build.platform, []):
                active_builds = Build.select(self.env, slave=slave.name,
                                             status=Build.IN_PROGRESS)
                if not list(active_builds):
                    slave.send_initiation(build)
                    return

    def _cleanup_orphaned_builds(self):
        # Remove all pending or in-progress builds
        db = self.env.get_db_cnx()
        for build in Build.select(self.env, status=Build.IN_PROGRESS, db=db):
            build.status = Build.PENDING
            build.update(db=db)
        for build in Build.select(self.env, status=Build.PENDING, db=db):
            build.delete(db=db)

    def _cleanup_snapshots(self, when):
        log.debug('Checking for unused snapshot archives...')
        for (config, rev, format), path in self.snapshots.items():
            keep = False
            for build in Build.select(self.env, config=config, rev=rev):
                if build.status not in (Build.SUCCESS, Build.FAILURE):
                    keep = True
                    break
            if not keep:
                log.info('Removing unused snapshot %s', path)
                os.unlink(path)
                del self.snapshots[(config, rev, format)]

    def get_snapshot(self, build, format):
        snapshot = self.snapshots.get((build.config, build.rev, format))
        if not snapshot:
            config = BuildConfig.fetch(self.env, build.config)
            snapshot = archive.pack(self.env, path=config.path, rev=build.rev,
                                    prefix=config.name, format=format)
            log.info('Prepared snapshot archive at %s' % snapshot)
            self.snapshots[(build.config, build.rev, format)] = snapshot
        return snapshot

    def register(self, handler):
        any_match = False
        for config in BuildConfig.select(self.env):
            for platform in TargetPlatform.select(self.env, config=config.name):
                if not platform.id in self.slaves:
                    self.slaves[platform.id] = set()
                match = True
                for property, pattern in ifilter(None, platform.rules):
                    try:
                        if not re.match(pattern, handler.info.get(property)):
                            match = False
                            break
                    except re.error, e:
                        log.error('Invalid platform matching pattern "%s"',
                                  pattern, exc_info=True)
                        match = False
                        break
                if match:
                    log.debug('Slave %s matched target platform %s',
                              handler.name, platform.name)
                    self.slaves[platform.id].add(handler)
                    any_match = True

        if not any_match:
            log.warning('Slave %s does not match any of the configured target '
                        'platforms', handler.name)
            return False

        self.schedule(self.check_interval * 0.2, self._check_build_queue)

        log.info('Registered slave "%s"', handler.name)
        return True

    def unregister(self, handler):
        for slaves in self.slaves.values():
            slaves.discard(handler)

        for build in Build.select(self.env, slave=handler.name,
                                  status=Build.IN_PROGRESS):
            log.info('Build [%s] of "%s" by %s cancelled', build.rev,
                     build.config, handler.name)
            build.slave = None
            build.status = Build.PENDING
            build.started = 0
            build.update()
            break
        log.info('Unregistered slave "%s"', handler.name)


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

    def handle_msg(self, msgno, payload):
        assert payload.content_type == beep.BEEP_XML
        elem = xmlio.parse(payload.body)

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
                self.channel.send_err(msgno, beep.Payload(xml))
                return

            xml = xmlio.Element('ok')
            self.channel.send_rpy(msgno, beep.Payload(xml))

    def send_initiation(self, build):
        log.info('Initiating build of "%s" on slave %s', build.config,
                 self.name)

        def handle_reply(cmd, msgno, ansno, payload):
            if cmd == 'ERR':
                if payload.content_type == beep.BEEP_XML:
                    elem = xmlio.parse(payload.body)
                    if elem.name == 'error':
                        log.warning('Slave %s refused build request: %s (%d)',
                                    self.name, elem.gettext(),
                                    int(elem.attr['code']))
                return

            elem = xmlio.parse(payload.body)
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
                self.channel.send_err(beep.Payload(xml))
                return
            self.send_snapshot(build, type, encoding)

        xml = xmlio.Element('build', recipe='recipe.xml')
        self.channel.send_msg(beep.Payload(xml), handle_reply=handle_reply)

    def send_snapshot(self, build, type, encoding):

        def handle_reply(cmd, msgno, ansno, payload):
            if cmd == 'ERR':
                assert payload.content_type == beep.BEEP_XML
                elem = xmlio.parse(payload.body)
                if elem.name == 'error':
                    log.warning('Slave %s did not accept archive: %s (%d)',
                                self.name, elem.gettext(),
                                int(elem.attr['code']))

            elif cmd == 'ANS':
                assert payload.content_type == beep.BEEP_XML
                db = self.env.get_db_cnx()
                elem = xmlio.parse(payload.body)
                if elem.name == 'started':
                    self._build_started(db, build, elem)
                elif elem.name == 'step':
                    self._build_step_completed(db, build, elem)
                elif elem.name == 'completed':
                    self._build_completed(db, build, elem)
                elif elem.name == 'aborted':
                    self._build_aborted(db, build, elem)
                elif elem.name == 'error':
                    build.status = Build.FAILURE
                build.update(db=db)
                db.commit()                    

        snapshot_format = {
            ('application/tar', 'bzip2'): 'bzip2',
            ('application/tar', 'gzip'): 'gzip',
            ('application/tar', None): 'tar',
            ('application/zip', None): 'zip',
        }[(type, encoding)]
        snapshot_path = self.master.get_snapshot(build, snapshot_format)
        snapshot_name = os.path.basename(snapshot_path)
        message = beep.Payload(file(snapshot_path), content_type=type,
                               content_disposition=snapshot_name,
                               content_encoding=encoding)
        self.channel.send_msg(message, handle_reply=handle_reply)

    def _build_started(self, db, build, elem):
        build.slave = self.name
        build.slave_info.update(self.info)
        build.started = int(_parse_iso_datetime(elem.attr['time']))
        build.status = Build.IN_PROGRESS
        log.info('Slave %s started build %d ("%s" as of [%s])',
                 self.name, build.id, build.config, build.rev)

    def _build_step_completed(self, db, build, elem):
        log.debug('Slave completed step "%s"', elem.attr['id'])
        step = BuildStep(self.env, build=build.id, name=elem.attr['id'],
                         description=elem.attr.get('description'))
        step.started = int(_parse_iso_datetime(elem.attr['time']))
        step.stopped = step.started + int(elem.attr['duration'])
        if elem.attr['result'] == 'failure':
            log.warning('Step failed: %s', elem.gettext())
            step.status = BuildStep.FAILURE
        else:
            step.status = BuildStep.SUCCESS

        # TODO: Insert log messages into separate table, and also store reports
        log_lines = []
        for log_elem in elem.children('log'):
            for messages_elem in log_elem.children('messages'):
                for message_elem in messages_elem.children('message'):
                    log_lines.append(message_elem.gettext())
        step.log = '\n'.join(log_lines)

        step.insert(db=db)

    def _build_completed(self, db, build, elem):
        log.info('Slave %s completed build %d ("%s" as of [%s])', self.name,
                 build.id, build.config, build.rev)
        build.stopped = int(_parse_iso_datetime(elem.attr['time']))
        if elem.attr['result'] == 'failure':
            build.status = Build.FAILURE
        else:
            build.status = Build.SUCCESS

    def _build_aborted(self, db, build, elem):
        log.info('Slave "%s" aborted build %d ("%s" as of [%s])',
                 self.name, build.id, build.config, build.rev)
        build.slave = None
        build.started = 0
        build.status = Build.PENDING
        build.slave_info = {}
        for step in BuildStep.select(self.env, build=build.id, db=db):
            step.delete(db=db)


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
                      metavar='HOSTNAME',
                      help='the host name or IP address to bind to')
    parser.add_option('-l', '--log', dest='logfile', metavar='FILENAME',
                      help='write log messages to FILENAME')
    parser.add_option('-i', '--interval', dest='interval', metavar='SECONDS',
                      default=DEFAULT_CHECK_INTERVAL, type='int',
                      help='poll interval for changeset detection')
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

    # Configure logging
    log = logging.getLogger('bitten')
    log.setLevel(options.loglevel)
    handler = logging.StreamHandler()
    if options.logfile:
        handler.setLevel(logging.WARNING)
    else:
        handler.setLevel(options.loglevel)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    log.addHandler(handler)
    if options.logfile:
        handler = logging.FileHandler(options.logfile)
        handler.setLevel(options.loglevel)
        formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: '
                                      '%(message)s')
        handler.setFormatter(formatter)
        log.addHandler(handler)

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
            log.warning('Reverse host name lookup failed (%s)', e)
            host = ip

    master = Master(env_path, host, port, check_interval=options.interval)
    try:
        master.run(timeout=5.0)
    except KeyboardInterrupt:
        master.quit()

if __name__ == '__main__':
    main()
