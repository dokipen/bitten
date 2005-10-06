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


def collect_changes(repos, config, db=None):
    """Collect all changes for a build configuration that either have already
    been built, or still need to be built.
    
    This function is a generator that yields `(platform, rev, build)` tuples,
    where `platform` is a `TargetPlatform` object, `rev` is the identifier of
    the changeset, and `build` is a `Build` object or `None`.
    """
    env = config.env
    if not db:
        db = env.get_db_cnx()
    node = repos.get_node(config.path)

    for path, rev, chg in node.get_history():

        # Don't follow moves/copies
        if path != repos.normalize_path(config.path):
            break

        # Stay within the limits of the build config
        if config.min_rev and repos.rev_older_than(rev, config.min_rev):
            break
        if config.max_rev and repos.rev_older_than(config.max_rev, rev):
            continue

        # Make sure the repository directory isn't empty at this
        # revision
        old_node = repos.get_node(path, rev)
        is_empty = True
        for entry in old_node.get_entries():
            is_empty = False
            break
        if is_empty:
            continue

        # For every target platform, check whether there's a build
        # of this revision
        for platform in TargetPlatform.select(env, config.name, db=db):
            builds = list(Build.select(env, config.name, rev, platform.id,
                                       db=db))
            if builds:
                build = builds[0]
            else:
                build = None

            yield platform, rev, build


class BuildQueue(object):
    """Enapsulates the build queue of an environment.
    
    A build queue manages the the registration of build slaves, creation and
    removal of snapshot archives, and detection of repository revisions that
    need to be built.
    """

    def __init__(self, env):
        """Create the build queue.
        
        @param env: The Trac environment
        """
        self.env = env
        self.slaves = {} # Sets of slave names keyed by target platform ID

        # Paths to generated snapshot archives, key is (config name, revision)
        self.snapshots = {}

        # Populate the snapshots index with existing archive files
        for config in BuildConfig.select(self.env):
            snapshots = archive.index(self.env, prefix=config.name)
            for rev, format, path in snapshots:
                self.snapshots[(config.name, rev, format)] = path

        # Clear any files in the snapshots directory that aren't in the archive
        # index. Those may be archives without corresponding checksum files,
        # i.e. here the creation of the snapshot was interrupted
        snapshots_dir = os.path.join(self.env.path, 'snapshots')
        for filename in os.listdir(snapshots_dir):
            filepath = os.path.join(snapshots_dir, filename)
            if filepath.endswith('.md5'):
                if filepath[:-4] not in self.snapshots.values():
                    os.remove(filepath)
            else:
                if filepath not in self.snapshots.values():
                    log.info('Removing file %s (not a valid snapshot archive)',
                             filename)
                    os.remove(filepath)

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
            for idx, slave in enumerate([name for name in slaves if name
                                         in available_slaves]):
                slaves.append(slaves.pop(idx)) # Round robin
                return build, slave

        return None, None

    def populate(self):
        """Add a build for the next change on each build configuration to the
        queue.

        The next change is the latest repository check-in for which there isn't
        a corresponding build on each target platform. Repeatedly calling this
        method will eventually result in the entire change history of the build
        configuration being in the build queue.
        """
        repos = self.env.get_repository()
        try:
            repos.sync()

            db = self.env.get_db_cnx()
            build = None
            insert_build = False
            for config in BuildConfig.select(self.env, db=db):
                for platform, rev, build in collect_changes(repos, config, db):
                    if build is None:
                        log.info('Enqueuing build of configuration "%s" at '
                                 'revision [%s] on %s', config.name, rev,
                                 platform.name)
                        build = Build(self.env)
                        build.config = config.name
                        build.rev = str(rev)
                        build.rev_time = repos.get_changeset(rev).date
                        build.platform = platform.id
                        insert_build = True
                        break
            if insert_build:
                build.insert(db=db)
                db.commit()
        finally:
            repos.close()

    def reset_orphaned_builds(self):
        """Reset all in-progress builds to `PENDING` state.
        
        This is used to cleanup after a crash of the build master process,
        which would leave in-progress builds in the database that aren't
        actually being built because the slaves have disconnected.
        """
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
        """Return the absolute path to a snapshot archive for the given build.
        The archive can be created if it doesn't exist yet.

        @param build: The `Build` object
        @param format: The archive format (one of `gzip`, `bzip2` or `zip`)
        @param create: Whether the archive should be created if it doesn't exist
                       yet
        @return: The absolute path to the create archive file, or None if the
                 snapshot doesn't exist and wasn't created
        """
        snapshot = self.snapshots.get((build.config, build.rev, format))
        if create and snapshot is None:
            config = BuildConfig.fetch(self.env, build.config)
            log.debug('Preparing snapshot archive for %s@%s' % (config.path,
                      build.rev))
            snapshot = archive.pack(self.env, path=config.path, rev=build.rev,
                                    prefix=config.name, format=format,
                                    overwrite=True)
            log.info('Prepared snapshot archive at %s' % snapshot)
            self.snapshots[(build.config, build.rev, format)] = snapshot
        return snapshot

    def remove_unused_snapshots(self):
        """Find any previously created snapshot archives that are no longer
        needed because all corresponding builds have already been completed.

        This method should be called in regular intervals to keep the total
        disk space occupied by the snapshot archives to a minimum.
        """
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
                if os.path.isfile(path + '.md5'):
                    os.remove(path + '.md5')
                del self.snapshots[(config, rev, format)]

    # Slave registry

    def register_slave(self, name, properties):
        """Register a build slave with the queue.
        
        @param name: The name of the slave
        @param properties: A `dict` containing the properties of the slave
        @return: whether the registration was successful

        This method tries to match the slave against the configured target
        platforms. Only if it matches at least one platform will the
        registration be successful.
        """
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
        """Unregister a build slave.
        
        @param name: The name of the slave
        @return: `True` if the slave was registered for this build queue,
                 `False` otherwise

        This method removes the slave from the registry, and also resets any
        in-progress builds by this slave to `PENDING` state.
        """
        for slaves in self.slaves.values():
            if name in slaves:
                slaves.remove(name)
                return True
        return False
