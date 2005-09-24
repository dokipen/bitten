# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

from ConfigParser import ConfigParser
from datetime import datetime
import logging
import os
import platform
import shutil
import tempfile

from bitten.build import BuildError
from bitten.recipe import Recipe, InvalidRecipeError
from bitten.util import archive, beep, xmlio

log = logging.getLogger('bitten.slave')


class Slave(beep.Initiator):
    """Build slave."""

    def __init__(self, ip, port, name=None, config=None, dry_run=False,
                 work_dir=None):
        beep.Initiator.__init__(self, ip, port)
        self.name = name
        self.config = config
        self.dry_run = dry_run
        if not work_dir:
            work_dir = tempfile.mkdtemp(prefix='bitten')
        elif not os.path.exists(work_dir):
            os.makedirs(work_dir)
        self.work_dir = work_dir

    def greeting_received(self, profiles):
        if OrchestrationProfileHandler.URI not in profiles:
            err = 'Peer does not support the Bitten orchestration profile'
            log.error(err)
            raise beep.TerminateSession, err
        self.channels[0].profile.send_start([OrchestrationProfileHandler])


class OrchestrationProfileHandler(beep.ProfileHandler):
    """Handler for communication on the Bitten build orchestration profile from
    the perspective of the build slave.
    """
    URI = 'http://bitten.cmlenz.net/beep/orchestration'

    def handle_connect(self):
        """Register with the build master."""
        self.recipe_xml = None

        def handle_reply(cmd, msgno, ansno, payload):
            if cmd == 'ERR':
                if payload.content_type == beep.BEEP_XML:
                    elem = xmlio.parse(payload.body)
                    if elem.name == 'error':
                        log.error('Slave registration failed: %s (%d)',
                                  elem.gettext(), int(elem.attr['code']))
                raise beep.TerminateSession, 'Registration failed!'
            log.info('Registration successful')

        family = os.name
        system, node, release, version, machine, processor = platform.uname()
        system, release, version = platform.system_alias(system, release,
                                                         version)
        if self.session.name is not None:
            node = self.session.name
        else:
            node = node.split('.', 1)[0].lower()

        packages = []
        if self.session.config is not None:
            log.debug('Merging configuration from %s', self.session.config)
            config = ConfigParser()
            config.read(self.session.config)
            for section in config.sections():
                if section == 'machine':
                    machine = config.get(section, 'name', machine)
                    processor = config.get(section, 'processor', processor)
                elif section == 'os':
                    system = config.get(section, 'name', system)
                    family = config.get(section, 'family', os.name)
                    release = config.get(section, 'version', release)
                else: # a package
                    attrs = {}
                    for option in config.options(section):
                        attrs[option] = config.get(section, option)
                    packages.append(xmlio.Element('package', name=section,
                                                  **attrs))

        log.info('Registering with build master as %s', node)
        xml = xmlio.Element('register', name=node)[
            xmlio.Element('platform', processor=processor)[machine],
            xmlio.Element('os', family=family, version=release)[system],
            xmlio.Fragment()[packages]
        ]
        self.channel.send_msg(beep.Payload(xml), handle_reply)

    def handle_msg(self, msgno, payload):
        if payload.content_type == beep.BEEP_XML:
            elem = xmlio.parse(payload.body)
            if elem.name == 'build':
                self.recipe_xml = elem
                # Received a build request
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
            archive_path = os.path.join(self.session.work_dir, archive_name)

            archive_file = file(archive_path, 'wb')
            try:
                shutil.copyfileobj(payload.body, archive_file)
            finally:
                archive_file.close()
            os.chmod(archive_path, 0400)

            log.debug('Received snapshot archive: %s', archive_path)

            # Unpack the archive
            try:
                prefix = archive.unpack(archive_path, self.session.work_dir)
                path = os.path.join(self.session.work_dir, prefix)
                os.chmod(path, 0700)
                log.debug('Unpacked snapshot to %s' % path)
            except archive.Error, e:
                xml = xmlio.Element('error', code=550)[
                    'Could not unpack archive (%s)' % e
                ]
                self.channel.send_err(msgno, beep.Payload(xml))
                log.error('Could not unpack archive %s: %s', archive_path, e,
                          exc_info=True)
                return

            try:
                self.execute_build(msgno, Recipe(self.recipe_xml, path))
            finally:
                shutil.rmtree(path)
                os.unlink(archive_path)

    def execute_build(self, msgno, recipe):
        log.info('Building in directory %s', recipe.ctxt.basedir)
        try:
            if not self.session.dry_run:
                xml = xmlio.Element('started',
                                    time=datetime.utcnow().isoformat())
                self.channel.send_ans(msgno, beep.Payload(xml))

            failed = False
            for step in recipe:
                log.info('Executing build step "%s"', step.id)
                started = datetime.utcnow()
                try:
                    xml = xmlio.Element('step', id=step.id,
                                        description=step.description,
                                        time=started.isoformat())
                    step_failed = False
                    try:
                        for type, category, generator, output in \
                                step.execute(recipe.ctxt):
                            if type == Recipe.ERROR:
                                step_failed = True
                            xml.append(xmlio.Element(type, category=category,
                                                     generator=generator)[
                                output
                            ])
                    except BuildError, e:
                        log.error('Build step %s failed', step.id)
                        failed = True
                    xml.attr['duration'] = (datetime.utcnow() - started).seconds
                    if step_failed:
                        xml.attr['result'] = 'failure'
                        log.warning('Build step %s failed', step.id)
                    else:
                        xml.attr['result'] = 'success'
                        log.info('Build step %s completed successfully',
                                 step.id)
                    if not self.session.dry_run:
                        self.channel.send_ans(msgno, beep.Payload(xml))
                except InvalidRecipeError, e:
                    log.warning('Build step %s failed: %s', step.id, e)
                    duration = datetime.utcnow() - started
                    failed = True
                    xml = xmlio.Element('step', id=step.id, result='failure',
                                        description=step.description,
                                        time=started.isoformat(),
                                        duration=duration.seconds)[
                        xmlio.Element('error')[e]
                    ]
                    if not self.session.dry_run:
                        self.channel.send_ans(msgno, beep.Payload(xml))

            if failed:
                log.warning('Build failed')
            else:
                log.info('Build completed successfully')
            if not self.session.dry_run:
                xml = xmlio.Element('completed', time=datetime.utcnow().isoformat(),
                                    result=['success', 'failure'][failed])
                self.channel.send_ans(msgno, beep.Payload(xml))

                self.channel.send_nul(msgno)
            else:
                xml = xmlio.Element('error', code=550)['Dry run']
                self.channel.send_err(msgno, beep.Payload(xml))

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
    parser.add_option('--name', action='store', dest='name',
                      help='name of this slave (defaults to host name)')
    parser.add_option('-f', '--config', action='store', dest='config',
                      metavar='FILE', help='path to configuration file')
    parser.add_option('-d', '--work-dir', action='store', dest='work_dir',
                      metavar='DIR', help='working directory for builds')
    parser.add_option('-n', '--dry-run', action='store_const', dest='dry_run',
                      const=True, help='don\'t report results back to master')
    parser.add_option('--debug', action='store_const', dest='loglevel',
                      const=logging.DEBUG, help='enable debugging output')
    parser.add_option('-v', '--verbose', action='store_const', dest='loglevel',
                      const=logging.INFO, help='print as much as possible')
    parser.add_option('-q', '--quiet', action='store_const', dest='loglevel',
                      const=logging.ERROR, help='print as little as possible')
    parser.set_defaults(dry_run=False, loglevel=logging.WARNING)
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

    logger = logging.getLogger('bitten')
    logger.setLevel(options.loglevel)
    handler = logging.StreamHandler()
    handler.setLevel(options.loglevel)
    formatter = logging.Formatter('[%(levelname)-8s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    slave = Slave(host, port, name=options.name, config=options.config,
                  dry_run=options.dry_run, work_dir=options.work_dir)
    try:
        slave.run()
    except KeyboardInterrupt:
        slave.quit()

    if os.path.isdir(slave.work_dir):
        shutil.rmtree(slave.work_dir)

if __name__ == '__main__':
    main()
