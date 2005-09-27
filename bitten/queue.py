# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

from itertools import ifilter
import logging
import os
import re

from bitten.model import BuildConfig, TargetPlatform, Build, BuildStep
from bitten.util import archive

log = logging.getLogger('bitten.queue')


class BuildQueue(object):
    """Enapsulates the build queue of an environment."""

    def __init__(self, env):
        self.env = env
        self.slaves = {} # Sets of slave names keyed by target platform ID

        # path to generated snapshot archives, key is (config name, revision)
        self.snapshots = {}
        for config in BuildConfig.select(self.env):
            snapshots = archive.index(self.env, prefix=config.name)
            for rev, format, path in snapshots:
                self.snapshots[(config.name, rev, format)] = path

        self.reset_orphaned_builds()
        self.remove_unused_snapshots()

    # Build scheduling

    def get_next_pending_build(self, available_slaves):
        """Check whether one of the pending builds can be built by one of the
        available build slaves.
        
        If such a build is found, this method returns a `(build, slave)` tuple,
        where `build` is the `Build` object and `slave` is the name of the
        build slave.

        Otherwise, this function will return `(None, None)`.
        """
        log.debug('Checking for pending builds...')

        for build in Build.select(self.env, status=Build.PENDING):

            # Ignore pending builds for deactived build configs
            config = BuildConfig.fetch(self.env, name=build.config)
            if not config.active:
                continue

            # Find a slave for the build platform that is not already building
            # something else
            slaves = self.slaves.get(build.platform, [])
            for slave in [name for name in slaves if name in available_slaves]:
                slaves.remove(slave)
                slaves.append(slave)
                return build, slave

        return None, None

    def populate(self):
        repos = self.env.get_repository()
        try:
            repos.sync()

            db = self.env.get_db_cnx()
            for config in BuildConfig.select(self.env, db=db):
                log.debug('Checking for changes to "%s" at %s', config.label,
                          config.path)
                node = repos.get_node(config.path)
                for path, rev, chg in node.get_history():

                    # Don't follow moves/copies
                    if path != repos.normalize_path(config.path):
                        break

                    # Make sure the repository directory isn't empty at this
                    # revision
                    old_node = repos.get_node(path, rev)
                    is_empty = True
                    for entry in old_node.get_entries():
                        is_empty = False
                        break
                    if is_empty:
                        continue

                    enqueued = False
                    for platform in TargetPlatform.select(self.env,
                                                          config.name, db=db):
                        # Check whether this revision of the configuration has
                        # already been built on this platform
                        builds = Build.select(self.env, config.name, rev,
                                              platform.id, db=db)
                        if not list(builds):
                            log.info('Enqueuing build of configuration "%s" at '
                                     'revision [%s] on %s', config.name, rev,
                                     platform.name)
                            build = Build(self.env)
                            build.config = config.name
                            build.rev = str(rev)
                            build.rev_time = repos.get_changeset(rev).date
                            build.platform = platform.id
                            build.insert(db)
                            enqueued = True
                    if enqueued:
                        db.commit()
                        break
        finally:
            repos.close()

    def reset_orphaned_builds(self):
        # Reset all in-progress builds
        db = self.env.get_db_cnx()
        for build in Build.select(self.env, status=Build.IN_PROGRESS, db=db):
            build.status = Build.PENDING
            build.slave = None
            build.slave_info = {}
            build.started = 0
            for step in list(BuildStep.select(self.env, build=build.id, db=db)):
                step.delete(db=db)
            build.update(db=db)
        db.commit()

    # Snapshot management

    def get_snapshot(self, build, format, create=False):
        snapshot = self.snapshots.get((build.config, build.rev, format))
        if create and snapshot is None:
            config = BuildConfig.fetch(self.env, build.config)
            snapshot = archive.pack(self.env, path=config.path, rev=build.rev,
                                    prefix=config.name, format=format)
            log.info('Prepared snapshot archive at %s' % snapshot)
            self.snapshots[(build.config, build.rev, format)] = snapshot
        return snapshot

    def remove_unused_snapshots(self):
        log.debug('Checking for unused snapshot archives...')
        for (config, rev, format), path in self.snapshots.items():
            keep = False
            for build in Build.select(self.env, config=config, rev=rev):
                if build.status not in (Build.SUCCESS, Build.FAILURE):
                    keep = True
                    break
            if not keep:
                log.info('Removing unused snapshot %s', path)
                os.remove(path)
                del self.snapshots[(config, rev, format)]

    # Slave registry

    def register_slave(self, name, properties):
        any_match = False
        for config in BuildConfig.select(self.env):
            for platform in TargetPlatform.select(self.env, config=config.name):
                if not platform.id in self.slaves:
                    self.slaves[platform.id] = []
                match = True
                for propname, pattern in ifilter(None, platform.rules):
                    try:
                        propvalue = properties.get(propname)
                        if not propvalue or not re.match(pattern, propvalue):
                            match = False
                            break
                    except re.error:
                        log.error('Invalid platform matching pattern "%s"',
                                  pattern, exc_info=True)
                        match = False
                        break
                if match:
                    log.debug('Slave %s matched target platform "%s"', name,
                              platform.name)
                    self.slaves[platform.id].append(name)
                    any_match = True
        return any_match

    def unregister_slave(self, name):
        for slaves in self.slaves.values():
            if name in slaves:
                slaves.remove(name)

        db = self.env.get_db_cnx()
        for build in Build.select(self.env, slave=name,
                                  status=Build.IN_PROGRESS, db=db):
            log.info('Build %d ("%s" as of [%s]) cancelled by  %s', build.id,
                     build.rev, build.config, name)
            for step in list(BuildStep.select(self.env, build=build.id)):
                step.delete(db=db)

            build.slave = None
            build.slave_info = {}
            build.status = Build.PENDING
            build.started = 0
            build.update(db=db)
            break

        db.commit()
