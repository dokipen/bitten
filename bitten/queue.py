# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

"""Implements the scheduling of builds for a project.

This module provides the functionality for scheduling builds for a specific
Trac environment. It is used by both the build master and the web interface to
get the list of required builds (revisions not built yet).

Furthermore, the C{BuildQueue} class is used by the build master to determine
the next pending build, and to match build slaves against configured target
platforms.
"""

from itertools import ifilter
import logging
import re

from bitten.model import BuildConfig, TargetPlatform, Build, BuildStep
from bitten.snapshot import SnapshotManager

log = logging.getLogger('bitten.queue')


def collect_changes(repos, config, db=None):
    """Collect all changes for a build configuration that either have already
    been built, or still need to be built.
    
    This function is a generator that yields C{(platform, rev, build)} tuples,
    where C{platform} is a L{bitten.model.TargetPlatform} object, C{rev} is the
    identifier of the changeset, and C{build} is a L{bitten.model.Build} object
    or C{None}.

    @param repos: the version control repository
    @param config: the build configuration
    @param db: a database connection (optional)
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

    def __init__(self, env, build_all=False):
        """Create the build queue.
        
        @param env: the Trac environment
        @param build_all: whether older revisions should be built
        """
        self.env = env
        self.build_all = build_all
        self.slaves = {} # Sets of slave names keyed by target platform ID

        # Snapshot managers, keyed by build config name
        self.snapshots = {}
        for config in BuildConfig.select(self.env, include_inactive=True):
            self.snapshots[config.name] = SnapshotManager(config)

        self.reset_orphaned_builds()

    # Build scheduling

    def get_next_pending_build(self, available_slaves):
        """Check whether one of the pending builds can be built by one of the
        available build slaves.
        
        If such a build is found, this method returns a C{(build, slave)}
        tuple, where C{build} is the L{bitten.model.Build} object and C{slave}
        is the name of the build slave that should handle the build.

        Otherwise, this function will return C{(None, None)}
        """
        log.debug('Checking for pending builds...')
	if len(available_slaves) == 0: 
            log.debug('No available slaves.')
            return None, None

        repos = self.env.get_repository()

	# delete any old builds.
        builds_to_delete = []
        try:
            for build in Build.select(self.env, status=Build.PENDING):
		if self.should_delete_build(build, repos):
		   builds_to_delete.append(build)
        finally:
            db = self.env.get_db_cnx()	
            for build in builds_to_delete:
                build.delete(db=db)

        # Rather than just take the first build available to 
        # this slave by version number, we'd like to ensure that
        # all the most recent revisions of each config are built
        # before we do any older ones. If all the most recent
        # revisions are done/in progress for our set of available
        # slaves, we'll just fall back to processing the remaining
        # builds in descending revision order. First thing we'll do is
	# figure out the newest revision that has a build for each config.

	# now make sure all the newest revisions of each config that can be
	# built are in-progress or done.
        for config in BuildConfig.select(self.env):	
	    # need to loop to get all target platforms of the
            # newest revision
	    newest_rev = -1
            for build in Build.select(self.env, config.name):
		if build.rev < newest_rev:
		   break
		if self.should_delete_build(build, repos):
		   continue
		newest_rev = build.rev

		if build.status == Build.PENDING:
   	            slaves = self.slaves.get(build.platform, [])
	            for idx, slave in enumerate([name for name in slaves
						 if name in available_slaves]):
                        slaves.append(slaves.pop(idx)) # Round robin 
                        return build, slave

	# now just assign anyone who's left
        for build in Build.select(self.env, status=Build.PENDING):
	    if self.should_delete_build(build, repos):
		continue
            # Find a slave for the build platform that is not already building
            # something else
            slaves = self.slaves.get(build.platform, [])
            for idx, slave in enumerate([name for name in slaves if name
                                         in available_slaves]):
                slaves.append(slaves.pop(idx)) # Round robin
                return build, slave

        log.debug('No pending builds.')
        return None, None

    def should_delete_build(self, build, repos):
        # Ignore pending builds for deactived build configs
        config = BuildConfig.fetch(self.env, build.config)
        if not config.active:	
            log.info('Dropping build of configuration "%s" at '
                     'revision [%s] on "%s" because the configuration is '
                     'deactivated', config.name, build.rev, TargetPlatform.fetch(self.env, build.platform).name)
            return True
        # Stay within the revision limits of the build config
        if (config.min_rev and repos.rev_older_than(build.rev,
                                                    config.min_rev)) \
        or (config.max_rev and repos.rev_older_than(config.max_rev,
                                                    build.rev)):
            # This minimum and/or maximum revision has changed since
            # this build was enqueued, so drop it
            log.info('Dropping build of configuration "%s" at '
                     'revision [%s] on "%s" because it is outside of the '
                     'revision range of the configuration', config.name,
                     build.rev, TargetPlatform.fetch(self.env, build.platform).name)
	    return True
	return False

    def populate(self):
        """Add a build for the next change on each build configuration to the
        queue.

        The next change is the latest repository check-in for which there isn't
        a corresponding build on each target platform. Repeatedly calling this
        method will eventually result in the entire change history of the build
        configuration being in the build queue.
        """
        repos = self.env.get_repository()
        if hasattr(repos, 'sync'):
            repos.sync()

        db = self.env.get_db_cnx()
        builds = []
        for config in BuildConfig.select(self.env, db=db):
            for platform, rev, build in collect_changes(repos, config, db):
                if build is None:
                    log.info('Enqueuing build of configuration "%s" at '
                             'revision [%s] on %s', config.name, rev,
                             platform.name)
                    build = Build(self.env, config=config.name,
                                  platform=platform.id, rev=str(rev),
                                  rev_time = repos.get_changeset(rev).date)
                    builds.append(build)
                    break
                elif not self.build_all:
                    break
        for build in builds:
            build.insert(db=db)
        db.commit()

    def reset_orphaned_builds(self):
        """Reset all in-progress builds to PENDING state.
        
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

    # Slave registry

    def register_slave(self, name, properties):
        """Register a build slave with the queue.
        
        This method tries to match the slave against the configured target
        platforms. Only if it matches at least one platform will the
        registration be successful.
        
        @param name: The name of the slave
        @param properties: A dict containing the properties of the slave
        @return: Whether the registration was successful
        """
        any_match = False
        for config in BuildConfig.select(self.env):
            for platform in TargetPlatform.select(self.env, config=config.name):
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
                    self.slaves.setdefault(platform.id, []).append(name)
                    any_match = True
        return any_match

    def unregister_slave(self, name):
        """Unregister a build slave.
        
        This method removes the slave from the registry, and also resets any
        in-progress builds by this slave to PENDING state.
        
        @param name: The name of the slave
        @return: C{True} if the slave was registered for this build queue,
            C{False} otherwise
        """
        for slaves in self.slaves.values():
            if name in slaves:
                slaves.remove(name)
                return True
        return False
