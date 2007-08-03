# -*- coding: utf-8 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

"""Build master implementation."""

import calendar
from datetime import datetime, timedelta
import logging
import os
import re
try:
    set
except NameError:
    from sets import Set as set
import sys
import time

from trac.config import BoolOption, IntOption
from trac.core import *
from trac.env import Environment
from trac.web import IRequestHandler, HTTPBadRequest, HTTPConflict, \
                     HTTPForbidden, HTTPMethodNotAllowed, HTTPNotFound, \
                     RequestDone

from bitten.model import BuildConfig, Build, BuildStep, BuildLog, Report
from bitten.queue import BuildQueue
from bitten.recipe import Recipe
from bitten.trac_ext.main import BuildSystem
from bitten.util import xmlio


class BuildMaster(Component):
    """BEEP listener implementation for the build master."""

    implements(IRequestHandler)

    # Configuration options

    adjust_timestamps = BoolOption('bitten', 'adjust_timestamps', False, doc=
        """Whether the timestamps of builds should be adjusted to be close '
        to the timestamps of the corresponding changesets.""")

    build_all = BoolOption('bitten', 'build_all', False, doc=
        """Whether to request builds of older revisions even if a younger
        revision has already been built.""")

    slave_timeout = IntOption('bitten', 'slave_timeout', 3600, doc=
        """The time in seconds after which a build is cancelled if the slave
        does not report progress.""")

    # IRequestHandler methods

    def match_request(self, req):
        match = re.match(r'/builds(?:/(\d+)(?:/(\w+)/([^/]+))?)?$',
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
                raise HTTPMethodNotAllowed('Method not allowed')
            return self._process_build_creation(req)

        build = Build.fetch(self.env, req.args['id'])
        if not build:
            raise HTTPNotFound('No such build')
        config = BuildConfig.fetch(self.env, build.config)

        if not req.args['collection']:
            return self._process_build_initiation(req, config, build)

        if req.method != 'PUT':
            raise HTTPMethodNotAllowed('Method not allowed')

        if req.args['collection'] == 'steps':
            return self._process_build_step(req, config, build,
                                            req.args['member'])
        else:
            raise HTTPNotFound('No such collection')

    def _process_build_creation(self, req):
        queue = BuildQueue(self.env, build_all=self.build_all)
        queue.populate()

        try:
            elem = xmlio.parse(req.read())
        except xmlio.ParseError, e:
            raise HTTPBadRequest('XML parser error')

        name = elem.attr['name']
        properties = {Build.IP_ADDRESS: req.remote_addr}
        self.log.info('Build slave %r connected from %s', name, req.remote_addr)

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

        build = queue.get_build_for_slave(name, properties)
        if not build:
            req.send_response(204)
            req.send_header('Content-Type', 'text/plain')
            req.write('No pending builds')
            raise RequestDone

        req.send_response(201)
        req.send_header('Content-Type', 'text/plain')
        req.send_header('Location', req.abs_href.builds(build.id))
        req.write('Build pending')
        raise RequestDone

    def _process_build_initiation(self, req, config, build):
        build.started = int(time.time())
        build.update()

        xml = xmlio.parse(config.recipe)
        xml.attr['path'] = config.path
        xml.attr['revision'] = build.rev
        body = str(xml)

        req.send_response(200)
        req.send_header('Content-Type', 'application/x-bitten+xml')
        req.send_header('Content-Length', str(len(body)))
        req.send_header('Content-Disposition',
                        'attachment; filename=recipe_%s_r%s.xml' %
                        (config.name, build.rev))
        req.write(body)
        raise RequestDone

    def _process_build_step(self, req, config, build, stepname):
        step = BuildStep.fetch(self.env, build=build.id, name=stepname)
        if step:
            raise HTTPConflict('Build step already exists')

        recipe = Recipe(xmlio.parse(config.recipe))
        index = None
        current_step = None
        for num, recipe_step in enumerate(recipe):
            if recipe_step.id == stepname:
                index = num
                current_step = recipe_step
        if index is None:
            raise HTTPForbidden('No such build step')
        last_step = index == num

        try:
            elem = xmlio.parse(req.read())
        except xmlio.ParseError, e:
            raise HTTPBadRequest('XML parser error')

        self.log.debug('Slave %s completed step %d (%s) with status %s',
                       build.slave, index, stepname, elem.attr['status'])

        db = self.env.get_db_cnx()

        step = BuildStep(self.env, build=build.id, name=stepname)
        try:
            step.started = int(_parse_iso_datetime(elem.attr['time']))
            step.stopped = step.started + float(elem.attr['duration'])
        except ValueError, e:
            raise HTTPBadRequest(e.args[0])
        if elem.attr['status'] == 'failure':
            self.log.warning('Build %s step %s failed', build.id, stepname)
            step.status = BuildStep.FAILURE
        else:
            step.status = BuildStep.SUCCESS
        step.errors += [error.gettext() for error in elem.children('error')]
        step.insert(db=db)

        # Collect log messages from the request body
        for idx, log_elem in enumerate(elem.children('log')):
            build_log = BuildLog(self.env, build=build.id, step=step.name,
                                 generator=log_elem.attr.get('generator'),
                                 orderno=idx)
            for message_elem in log_elem.children('message'):
                build_log.messages.append((message_elem.attr['level'],
                                           message_elem.gettext()))
            build_log.insert(db=db)

        # Collect report data from the request body
        for report_elem in elem.children('report'):
            report = Report(self.env, build=build.id, step=step.name,
                            category=report_elem.attr.get('category'),
                            generator=report_elem.attr.get('generator'))
            for item_elem in report_elem.children():
                item = {'type': item_elem.name}
                item.update(item_elem.attr)
                for child_elem in item_elem.children():
                    item[child_elem.name] = child_elem.gettext()
                report.items.append(item)
            report.insert(db=db)

        # If this was the last step in the recipe we mark the build as
        # completed
        if last_step or step.status == BuildStep.FAILURE and \
                current_step.onerror == 'fail':
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
        req.send_response(200)
        req.send_header('Content-Type', 'text/plain')
        req.send_header('Content-Length', str(len(body)))
        req.write(body)
        raise RequestDone


def _parse_iso_datetime(string):
    """Minimal parser for ISO date-time strings.
    
    Return the time as floating point number. Only handles UTC timestamps
    without time zone information."""
    try:
        string = string.split('.', 1)[0] # strip out microseconds
        return calendar.timegm(time.strptime(string, '%Y-%m-%dT%H:%M:%S'))
    except ValueError, e:
        raise ValueError('Invalid ISO date/time %r' % string)
