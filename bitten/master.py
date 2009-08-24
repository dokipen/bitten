# -*- coding: utf-8 -*-
#
# Copyright (C) 2007 Edgewall Software
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

"""Build master implementation."""

import calendar
import re
import time
from StringIO import StringIO

from trac.attachment import Attachment
from trac.config import BoolOption, IntOption, Option
from trac.core import *
from trac.resource import ResourceNotFound
from trac.web import IRequestHandler, RequestDone

from bitten.model import BuildConfig, Build, BuildStep, BuildLog, Report, \
                     TargetPlatform

from bitten.main import BuildSystem
from bitten.queue import BuildQueue
from bitten.recipe import Recipe
from bitten.util import xmlio

__all__ = ['BuildMaster']
__docformat__ = 'restructuredtext en'


HTTP_BAD_REQUEST = 400
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_METHOD_NOT_ALLOWED = 405
HTTP_CONFLICT = 409


class BuildMaster(Component):
    """Trac request handler implementation for the build master."""

    implements(IRequestHandler)

    # Configuration options

    adjust_timestamps = BoolOption('bitten', 'adjust_timestamps', False, doc=
        """Whether the timestamps of builds should be adjusted to be close
        to the timestamps of the corresponding changesets.""")

    build_all = BoolOption('bitten', 'build_all', False, doc=
        """Whether to request builds of older revisions even if a younger
        revision has already been built.""")
    
    stabilize_wait = IntOption('bitten', 'stabilize_wait', 0, doc=
        """The time in seconds to wait for the repository to stabilize before
        queuing up a new build.  This allows time for developers to check in
        a group of related changes back to back without spawning multiple
        builds.""")

    slave_timeout = IntOption('bitten', 'slave_timeout', 3600, doc=
        """The time in seconds after which a build is cancelled if the slave
        does not report progress.""")

    logs_dir = Option('bitten', 'logs_dir', "log/bitten", doc=
         """The directory on the server in which client log files will be stored.""")

    quick_status = BoolOption('bitten', 'quick_status', False, doc=
         """Whether to show the current build status withing the Trac main 
            navigation bar""")

    def __init__(self):
        self.env.systeminfo.append(('Bitten',
                __import__('bitten', ['__version__']).__version__))

    # IRequestHandler methods

    def match_request(self, req):
        match = re.match(r'/builds(?:/(\d+)(?:/(\w+)/([^/]+)?)?)?$',
                         req.path_info)
        if match:
            if match.group(1):
                req.args['id'] = match.group(1)
                req.args['collection'] = match.group(2)
                req.args['member'] = match.group(3)
            return True

    def process_request(self, req):
        req.perm.assert_permission('BUILD_EXEC')

        if 'id' not in req.args:
            if req.method != 'POST':
                self._send_error(req, HTTP_METHOD_NOT_ALLOWED,
                                      'Only POST allowed for build creation')
            return self._process_build_creation(req)

        build = Build.fetch(self.env, req.args['id'])
        if not build:
            self._send_error(req, HTTP_NOT_FOUND,
                                  'No such build (%s)' % req.args['id'])
        config = BuildConfig.fetch(self.env, build.config)

        if not req.args['collection']:
            if req.method == 'DELETE':
                return self._process_build_cancellation(req, config, build)
            else:
                return self._process_build_initiation(req, config, build)

        if req.method != 'POST':
            self._send_error(req, HTTP_METHOD_NOT_ALLOWED,
                                  'Method %s not allowed' % req.method)

        if req.args['collection'] == 'steps':
            return self._process_build_step(req, config, build)
        else:
            self._send_error(req, HTTP_NOT_FOUND,
                    "No such collection '%s'" % req.args['collection'])

    # Internal methods

    def _send_response(self, req, code=200, body='', headers=None):
        """ Formats and sends the response, raising ``RequestDone``. """
        req.send_response(code)
        headers = headers or {}
        for header in headers:
            req.send_header(header, headers[header])
        req.write(body)
        raise RequestDone

    def _send_error(self, req, code=500, message=''):
        """ Formats and sends the error, raising ``RequestDone``. """
        headers = {'Content-Type': 'text/plain',
                   'Content-Length': str(len(message))}
        self._send_response(req, code, body=message, headers=headers)

    def _process_build_creation(self, req):
        queue = BuildQueue(self.env, build_all=self.build_all, 
                           stabilize_wait=self.stabilize_wait,
                           timeout=self.slave_timeout)
        queue.populate()

        try:
            elem = xmlio.parse(req.read())
        except xmlio.ParseError, e:
            self.log.error('Error parsing build initialization request: %s', e,
                           exc_info=True)
            self._send_error(req, HTTP_BAD_REQUEST, 'XML parser error')

        slavename = elem.attr['name']
        properties = {'name': slavename, Build.IP_ADDRESS: req.remote_addr}
        self.log.info('Build slave %r connected from %s', slavename,
                      req.remote_addr)

        for child in elem.children():
            if child.name == 'platform':
                properties[Build.MACHINE] = child.gettext()
                properties[Build.PROCESSOR] = child.attr.get('processor')
            elif child.name == 'os':
                properties[Build.OS_NAME] = child.gettext()
                properties[Build.OS_FAMILY] = child.attr.get('family')
                properties[Build.OS_VERSION] = child.attr.get('version')
            elif child.name == 'package':
                for name, value in child.attr.items():
                    if name == 'name':
                        continue
                    properties[child.attr['name'] + '.' + name] = value

        self.log.debug('Build slave configuration: %r', properties)

        build = queue.get_build_for_slave(slavename, properties)
        if not build:
            self._send_response(req, 204, '', {})

        self._send_response(req, 201, 'Build pending', headers={
                            'Content-Type': 'text/plain',
                            'Location': req.abs_href.builds(build.id)})

    def _process_build_cancellation(self, req, config, build):
        self.log.info('Build slave %r cancelled build %d', build.slave,
                      build.id)
        build.status = Build.PENDING
        build.slave = None
        build.slave_info = {}
        build.started = 0
        db = self.env.get_db_cnx()
        for step in list(BuildStep.select(self.env, build=build.id, db=db)):
            step.delete(db=db)
        build.update(db=db)
        db.commit()

        for listener in BuildSystem(self.env).listeners:
            listener.build_aborted(build)

        self._send_response(req, 204, '', {})

    def _process_build_initiation(self, req, config, build):
        self.log.info('Build slave %r initiated build %d', build.slave,
                      build.id)
        build.started = int(time.time())
        build.update()

        for listener in BuildSystem(self.env).listeners:
            listener.build_started(build)

        xml = xmlio.parse(config.recipe)
        xml.attr['path'] = config.path
        xml.attr['revision'] = build.rev
        xml.attr['config'] = config.name
        xml.attr['build'] = str(build.id)
        target_platform = TargetPlatform.fetch(self.env, build.platform)
        xml.attr['platform'] = target_platform.name
        xml.attr['name'] = build.slave
        body = str(xml)

        self.log.info('Build slave %r initiated build %d', build.slave,
                      build.id)

        self._send_response(req, 200, body, headers={
                    'Content-Type': 'application/x-bitten+xml',
                    'Content-Length': str(len(body)),
                    'Content-Disposition':
                        'attachment; filename=recipe_%s_r%s.xml' %
                        (config.name, build.rev)})

    def _process_build_step(self, req, config, build):
        try:
            elem = xmlio.parse(req.read())
        except xmlio.ParseError, e:
            self.log.error('Error parsing build step result: %s', e,
                           exc_info=True)
            self._send_error(req, HTTP_BAD_REQUEST, 'XML parser error')
        stepname = elem.attr['step']

        # make sure it's the right slave.
        if build.status != Build.IN_PROGRESS or \
                build.slave_info.get(Build.IP_ADDRESS) != req.remote_addr:
            self._send_error(req, HTTP_FORBIDDEN,
                                'Build %s has been invalidated for host %s.'
                                        % (build.id, req.remote_addr))

        step = BuildStep.fetch(self.env, build=build.id, name=stepname)
        if step:
            self._send_error(req, HTTP_CONFLICT, 'Build step already exists')

        recipe = Recipe(xmlio.parse(config.recipe))
        index = None
        current_step = None
        for num, recipe_step in enumerate(recipe):
            if recipe_step.id == stepname:
                index = num
                current_step = recipe_step
        if index is None:
            self._send_error(req, HTTP_FORBIDDEN,
                                'No such build step' % stepname)
        last_step = index == num

        self.log.debug('Slave %s (build %d) completed step %d (%s) with '
                       'status %s', build.slave, build.id, index, stepname,
                       elem.attr['status'])

        db = self.env.get_db_cnx()

        step = BuildStep(self.env, build=build.id, name=stepname)
        try:
            step.started = int(_parse_iso_datetime(elem.attr['time']))
            step.stopped = step.started + float(elem.attr['duration'])
        except ValueError, e:
            self.log.error('Error parsing build step timestamp: %s', e,
                           exc_info=True)
            self._send_error(req, HTTP_BAD_REQUEST, e.args[0])
        if elem.attr['status'] == 'failure':
            self.log.warning('Build %s step %s failed', build.id, stepname)
            step.status = BuildStep.FAILURE
            if current_step.onerror == 'fail':
                last_step = True
        else:
            step.status = BuildStep.SUCCESS
        step.errors += [error.gettext() for error in elem.children('error')]
        step.insert(db=db)

        # Collect log messages from the request body
        for idx, log_elem in enumerate(elem.children('log')):
            build_log = BuildLog(self.env, build=build.id, step=stepname,
                                 generator=log_elem.attr.get('generator'),
                                 orderno=idx)
            for message_elem in log_elem.children('message'):
                build_log.messages.append((message_elem.attr['level'],
                                           message_elem.gettext()))
            build_log.insert(db=db)

        # Collect report data from the request body
        for report_elem in elem.children('report'):
            report = Report(self.env, build=build.id, step=stepname,
                            category=report_elem.attr.get('category'),
                            generator=report_elem.attr.get('generator'))
            for item_elem in report_elem.children():
                item = {'type': item_elem.name}
                item.update(item_elem.attr)
                for child_elem in item_elem.children():
                    item[child_elem.name] = child_elem.gettext()
                report.items.append(item)
            report.insert(db=db)

        # Collect attachments from the request body
        for attach_elem in elem.children(Recipe.ATTACH):
            attach_elem = list(attach_elem.children('file'))[0] # One file only
            filename = attach_elem.attr.get('filename')
            resource_id = attach_elem.attr.get('resource') == 'config' \
                                    and build.config or build.resource.id
            try: # Delete attachment if it already exists
                old_attach = Attachment(self.env, 'build',
                                    parent_id=resource_id, filename=filename)
                old_attach.delete()
            except ResourceNotFound:
                pass
            attachment = Attachment(self.env, 'build', parent_id=resource_id)
            attachment.description = attach_elem.attr.get('description')
            attachment.author = req.authname
            fileobj = StringIO(attach_elem.gettext().decode('base64'))
            attachment.insert(filename, fileobj, fileobj.len, db=db)

        # If this was the last step in the recipe we mark the build as
        # completed
        if last_step:
            self.log.info('Slave %s completed build %d ("%s" as of [%s])',
                          build.slave, build.id, build.config, build.rev)
            build.stopped = step.stopped

            # Determine overall outcome of the build by checking the outcome
            # of the individual steps against the "onerror" specification of
            # each step in the recipe
            for num, recipe_step in enumerate(recipe):
                step = BuildStep.fetch(self.env, build.id, recipe_step.id)
                if step.status == BuildStep.FAILURE:
                    if recipe_step.onerror != 'ignore':
                        build.status = Build.FAILURE
                        break
            else:
                build.status = Build.SUCCESS

            build.update(db=db)

        db.commit()

        if last_step:
            for listener in BuildSystem(self.env).listeners:
                listener.build_completed(build)

        body = 'Build step processed'
        self._send_response(req, 201, body, {
                            'Content-Type': 'text/plain',
                            'Content-Length': str(len(body)),
                            'Location': req.abs_href.builds(
                                    build.id, 'steps', stepname)})


def _parse_iso_datetime(string):
    """Minimal parser for ISO date-time strings.
    
    Return the time as floating point number. Only handles UTC timestamps
    without time zone information."""
    try:
        string = string.split('.', 1)[0] # strip out microseconds
        return calendar.timegm(time.strptime(string, '%Y-%m-%dT%H:%M:%S'))
    except ValueError, e:
        raise ValueError('Invalid ISO date/time %r' % string)
