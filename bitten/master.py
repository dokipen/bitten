# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

from datetime import datetime, timedelta
import logging
import os
try:
    set
except NameError:
    from sets import Set as set
import sys
import time

from trac.env import Environment
from bitten.model import BuildConfig, Build, BuildStep, BuildLog, Report
from bitten.queue import BuildQueue
from bitten.trac_ext.main import BuildSystem
from bitten.util import archive, beep, xmlio

log = logging.getLogger('bitten.master')

DEFAULT_CHECK_INTERVAL = 120 # 2 minutes


class Master(beep.Listener):

    def __init__(self, envs, ip, port, adjust_timestamps=False,
                 check_interval=DEFAULT_CHECK_INTERVAL):
        beep.Listener.__init__(self, ip, port)
        self.profiles[OrchestrationProfileHandler.URI] = \
                OrchestrationProfileHandler
        self.adjust_timestamps = adjust_timestamps
        self.check_interval = check_interval
        self.handlers = {} # Map of connected slaves keyed by name

        self.queues = []
        for env in envs:
            self.queues.append(BuildQueue(env))

        self.schedule(self.check_interval, self._enqueue_builds)

    def close(self):
        for queue in self.queues:
            queue.reset_orphaned_builds()
        beep.Listener.close(self)

    def _cleanup(self, when):
        for queue in self.queues:
            queue.remove_unused_snapshots()

    def _enqueue_builds(self, when):
        self.schedule(self.check_interval, self._enqueue_builds)

        for queue in self.queues:
            queue.populate()

        self.schedule(self.check_interval * 0.2, self._initiate_builds)
        self.schedule(self.check_interval * 1.8, self._cleanup)

    def _initiate_builds(self, when):
        available_slaves = set([name for name in self.handlers
                                if not self.handlers[name].building])

        for idx, queue in enumerate(self.queues[:]):
            build, slave = queue.get_next_pending_build(available_slaves)
            if build:
                self.handlers[slave].send_initiation(queue, build)
                available_slaves.discard(slave)
                self.queues.append(self.queues.pop(idx)) # Round robin

    def register(self, handler):
        any_match = False
        for queue in self.queues:
            if queue.register_slave(handler.name, handler.info):
                any_match = True

        if not any_match:
            log.warning('Slave %s does not match any of the configured target '
                        'platforms', handler.name)
            return False

        self.handlers[handler.name] = handler
        self.schedule(self.check_interval * 0.2, self._initiate_builds)

        log.info('Registered slave "%s"', handler.name)
        return True

    def unregister(self, handler):
        if handler.name not in self.handlers:
            return

        for queue in self.queues:
            if queue.unregister_slave(handler.name):
                for build in list(Build.select(queue.env, slave=handler.name,
                                               status=Build.IN_PROGRESS)):
                    handler._build_aborted(queue, build)

        del self.handlers[handler.name]

        log.info('Unregistered slave "%s"', handler.name)


class OrchestrationProfileHandler(beep.ProfileHandler):
    """Handler for communication on the Bitten build orchestration profile from
    the perspective of the build master.
    """
    URI = 'http://bitten.cmlenz.net/beep/orchestration'

    def handle_connect(self):
        self.master = self.session.listener
        assert self.master
        self.name = None
        self.building = False
        self.info = {}

    def handle_disconnect(self):
        self.master.unregister(self)

    def handle_msg(self, msgno, payload):
        assert payload.content_type == beep.BEEP_XML
        elem = xmlio.parse(payload.body)

        if elem.name == 'register':
            self.name = elem.attr['name']
            self.info[Build.IP_ADDRESS] = self.session.addr[0]
            for child in elem.children():
                if child.name == 'platform':
                    self.info[Build.MACHINE] = child.gettext()
                    self.info[Build.PROCESSOR] = child.attr.get('processor')
                elif child.name == 'os':
                    self.info[Build.OS_NAME] = child.gettext()
                    self.info[Build.OS_FAMILY] = child.attr.get('family')
                    self.info[Build.OS_VERSION] = child.attr.get('version')
                elif child.name == 'package':
                    for name, value in child.attr.items():
                        if name == 'name':
                            continue
                        self.info[child.attr['name'] + '.' + name] = value

            if not self.master.register(self):
                xml = xmlio.Element('error', code=550)[
                    'Nothing for you to build here, please move along'
                ]
                self.channel.send_err(msgno, beep.Payload(xml))
                return

            xml = xmlio.Element('ok')
            self.channel.send_rpy(msgno, beep.Payload(xml))

    def send_initiation(self, queue, build):
        log.info('Initiating build of "%s" on slave %s', build.config,
                 self.name)
        self.building = True

        def handle_reply(cmd, msgno, ansno, payload):
            if cmd == 'ERR':
                if payload.content_type == beep.BEEP_XML:
                    elem = xmlio.parse(payload.body)
                    if elem.name == 'error':
                        log.warning('Slave %s refused build request: %s (%d)',
                                    self.name, elem.gettext(),
                                    int(elem.attr['code']))
                self.building = False
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
                self.building = False
                return
            self.send_snapshot(queue, build, type, encoding)

        config = BuildConfig.fetch(queue.env, build.config)
        self.channel.send_msg(beep.Payload(config.recipe),
                              handle_reply=handle_reply)

    def send_snapshot(self, queue, build, type, encoding):
        timestamp_delta = 0
        if self.master.adjust_timestamps:
            d = datetime.now() - timedelta(seconds=self.master.check_interval) \
                - datetime.fromtimestamp(build.rev_time)
            log.info('Warping timestamps by %s' % d)
            timestamp_delta = d.days * 86400 + d.seconds

        def handle_reply(cmd, msgno, ansno, payload):
            if cmd == 'ERR':
                assert payload.content_type == beep.BEEP_XML
                elem = xmlio.parse(payload.body)
                if elem.name == 'error':
                    log.warning('Slave %s refused to start build: %s (%d)',
                                self.name, elem.gettext(),
                                int(elem.attr['code']))
                self.building = False

            elif cmd == 'ANS':
                assert payload.content_type == beep.BEEP_XML
                elem = xmlio.parse(payload.body)
                if elem.name == 'started':
                    self._build_started(queue, build, elem, timestamp_delta)
                elif elem.name == 'step':
                    self._build_step_completed(queue, build, elem,
                                               timestamp_delta)
                elif elem.name == 'completed':
                    self._build_completed(queue, build, elem, timestamp_delta)
                elif elem.name == 'aborted':
                    self._build_aborted(queue, build)
                elif elem.name == 'error':
                    build.status = Build.FAILURE

            elif cmd == 'NUL':
                self.building = False

        snapshot_format = {
            ('application/tar', 'bzip2'): 'bzip2',
            ('application/tar', 'gzip'): 'gzip',
            ('application/tar', None): 'tar',
            ('application/zip', None): 'zip',
        }[(type, encoding)]
        snapshot_path = queue.get_snapshot(build, snapshot_format, create=True)
        snapshot_name = os.path.basename(snapshot_path)
        message = beep.Payload(file(snapshot_path, 'rb'), content_type=type,
                               content_disposition=snapshot_name,
                               content_encoding=encoding)
        self.channel.send_msg(message, handle_reply=handle_reply)

    def _build_started(self, queue, build, elem, timestamp_delta=None):
        build.slave = self.name
        build.slave_info.update(self.info)
        build.started = int(_parse_iso_datetime(elem.attr['time']))
        if timestamp_delta:
            build.started -= timestamp_delta
        build.status = Build.IN_PROGRESS
        build.update()

        log.info('Slave %s started build %d ("%s" as of [%s])',
                 self.name, build.id, build.config, build.rev)
        for listener in BuildSystem(queue.env).listeners:
            listener.build_started(build)

    def _build_step_completed(self, queue, build, elem, timestamp_delta=None):
        log.debug('Slave %s completed step "%s" with status %s', self.name,
                  elem.attr['id'], elem.attr['result'])

        db = queue.env.get_db_cnx()

        step = BuildStep(queue.env, build=build.id, name=elem.attr['id'],
                         description=elem.attr.get('description'))
        step.started = int(_parse_iso_datetime(elem.attr['time']))
        step.stopped = step.started + int(elem.attr['duration'])
        if timestamp_delta:
            step.started -= timestamp_delta
            step.stopped -= timestamp_delta
        if elem.attr['result'] == 'failure':
            log.warning('Step failed')
            step.status = BuildStep.FAILURE
        else:
            step.status = BuildStep.SUCCESS
        step.errors += [err.gettext() for err in elem.children('error')]
        step.insert(db=db)

        for idx, log_elem in enumerate(elem.children('log')):
            build_log = BuildLog(queue.env, build=build.id, step=step.name,
                                 generator=log_elem.attr.get('generator'),
                                 orderno=idx)
            for message_elem in log_elem.children('message'):
                build_log.messages.append((message_elem.attr['level'],
                                           message_elem.gettext()))
            build_log.insert(db=db)

        for report_elem in elem.children('report'):
            report = Report(queue.env, build=build.id, step=step.name,
                            category=report_elem.attr.get('category'),
                            generator=report_elem.attr.get('generator'))
            for item_elem in report_elem.children():
                item = {'type': item_elem.name}
                item.update(item_elem.attr)
                for child_elem in item_elem.children():
                    item[child_elem.name] = child_elem.gettext()
                report.items.append(item)
            report.insert(db=db)

        db.commit()

    def _build_completed(self, queue, build, elem, timestamp_delta=None):
        build.stopped = int(_parse_iso_datetime(elem.attr['time']))
        if timestamp_delta:
            build.stopped -= timestamp_delta
        if elem.attr['result'] == 'failure':
            build.status = Build.FAILURE
        else:
            build.status = Build.SUCCESS
        build.update()

        log.info('Slave %s completed build %d ("%s" as of [%s]) with status %s',
                 self.name, build.id, build.config, build.rev,
                 build.status == Build.FAILURE and 'FAILURE' or 'SUCCESS')
        for listener in BuildSystem(queue.env).listeners:
            listener.build_completed(build)

    def _build_aborted(self, queue, build):
        log.info('Slave %s aborted build %d ("%s" as of [%s])',
                 self.name, build.id, build.config, build.rev)
        for listener in BuildSystem(queue.env).listeners:
            listener.build_aborted(build)

        db = queue.env.get_db_cnx()

        for step in list(BuildStep.select(queue.env, build=build.id, db=db)):
            step.delete(db=db)

        build.slave = None
        build.slave_info = {}
        build.started = 0
        build.status = Build.PENDING
        build.update(db=db)

        db.commit()


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

    # Parse command-line arguments
    parser = OptionParser(usage='usage: %prog [options] ENV_PATHS',
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
    parser.add_option('--timewarp', action='store_true', dest='timewarp',
                      help='adjust timestamps of builds to be near the '
                           'timestamps of the corresponding changesets')
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

    # Configure logging
    logger = logging.getLogger('bitten')
    logger.setLevel(options.loglevel)
    handler = logging.StreamHandler()
    if options.logfile:
        handler.setLevel(logging.WARNING)
    else:
        handler.setLevel(options.loglevel)
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    if options.logfile:
        handler = logging.FileHandler(options.logfile)
        handler.setLevel(options.loglevel)
        formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: '
                                      '%(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)

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

    envs = []
    for arg in args:
        if not os.path.isdir(arg):
            log.warning('Ignoring %s: not a directory', arg)
            continue
        env = Environment(arg)
        if BuildSystem(env):
            if env.needs_upgrade():
                log.warning('Environment at %s needs to be upgraded', env.path)
                continue
            envs.append(env)
    if not envs:
        log.error('None of the specified environments has support for Bitten')
        sys.exit(2)

    master = Master(envs, host, port, adjust_timestamps=options.timewarp,
                    check_interval=options.interval)
    try:
        master.run(timeout=5.0)
    except KeyboardInterrupt:
        master.quit()

if __name__ == '__main__':
    main()
