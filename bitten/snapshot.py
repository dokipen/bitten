# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

"""Snapshot archive management.

Snapshots of the code base are stored in the Trac environment as tar archives,
compressed using bzip2.

These files use the naming convention C{[config_name]_r[revision].tar.bz2} so
they can be located programmatically after creation, and associated with the
build config and revision they apply to.

These snapshot files are accompanied by a checksum file (using MD5). Any archive
file with no accompanying checksum is considered incomplete or invalid.

For larger code bases, these snapshots may be relatively expensive to create.
Most of the time is spent in walking the repository directory and reading the
files it contains. To avoid blocking the build master while snapshots are
created, this is done in a worker thread.

As snapshot archives are often very similar to each other for subsequent
revisions, an attempt is made to avoid the creation of new archives from
scratch. Instead, the build master keeps the most recently used archives (MRU
cache) and will build new archives based on the deltas provided by the version
control system. Using the nearest existing snapshot as the base, deleted files
and directories are removed from the snapshot, added files/directories are
added, and modified files are updated.
"""

from datetime import datetime
import logging
import os
import posixpath
try:
    import threading
except ImportError:
    import dummy_threading as threading
import time
import tarfile

from bitten.util import md5sum

__all__ = ['SnapshotManager']

log = logging.getLogger('bitten.snapshot')

MAX_SNAPSHOTS = 10
SNAPSHOTS_DIR = 'snapshots'


class SnapshotManager(object):
    """Manages snapshot archives for a specific build configuration."""

    def __init__(self, config):
        """Create the snapshot manager.
        
        @param config: the build configuration
        @type config: an instance of L{bitten.model.BuildConfig}
        """
        assert config and config.exists, 'Build configuration does not exist'
        self.env = config.env
        self.config = config

        self.prefix = config.name
        self.directory = self.env.config.get('bitten', 'snapshots_dir',
                                             os.path.join(self.env.path,
                                                          SNAPSHOTS_DIR))
        self.limit = int(self.env.config.get('bitten', 'max_snapshots',
                                             MAX_SNAPSHOTS))

        # Create the snapshots directory if it doesn't already exist
        if not os.path.exists(self.directory):
            os.mkdir(self.directory)

        # Make sure we have permissions to write to the directory
        if not os.access(self.directory, os.R_OK + os.W_OK):
            raise IOError('Insufficient permissions to create snapshots in %s' %
                          self.directory)

        # Collect a list of all existing snapshot archives
        self._index = []
        for snapshot in self._scan():
            self._index.append(snapshot)
        self._lock = threading.RLock()
        self._cleanup()

        self._workers = {}

    def _scan(self):
        """Find all existing snapshots in the directory."""
        for filename in [f for f in os.listdir(self.directory)
                         if f.startswith(self.prefix)]:
            if not filename.endswith('.tar.bz2'):
                continue
            rest = filename[len(self.prefix):-8]
            if not rest.startswith('_r'):
                continue
            rev = rest[2:]

            filepath = os.path.join(self.directory, filename)
            try:
                md5sum.validate(filepath)
            except md5sum.IntegrityError, e:
                log.warning('Integrity error checking %s (%s)', filepath, e)
                os.remove(filepath)
                continue
            mtime = os.path.getmtime(filepath)

            yield mtime, rev, filepath

    def _cleanup(self, limit=None):
        """Remove obsolete snapshots to preserve disk space.
        
        @param limit: the maximum number of snapshot archives to keep; defaults
            to the value of the C{max_snapshots} value in C{trac.ini}.
        """
        self._lock.acquire()
        try:
            self._index.sort(lambda a, b: -cmp(a[0], b[0]))
            limit = limit or self.limit
            if len(self._index) > limit:
                for mtime, rev, path in self._index[limit:]:
                    log.debug('Removing snapshot %s', path)
                    os.remove(path)
                    md5file = path + '.md5'
                    if os.path.isfile(md5file):
                        os.remove(md5file)
                    else:
                        md5file = os.path.splitext(path)[0] + '.md5'
                        if os.path.isfile(md5file):
                            os.remove(md5file)
                self._index = self._index[:limit]
        finally:
            self._lock.release()

    def create(self, rev):
        """Create a new snapshot archive for the specified revision.
        
        The archive is created in a worker thread. The return value of this
        function is the thread object. The caller may use this object to check
        for completion of the operation.
        
        @param rev: the repository revision for which a snapshot archive should
            be created
        """
        self._lock.acquire()
        try:
            repos = self.env.get_repository()
            new_root = repos.get_node(self.config.path or '/', rev)
            assert new_root.isdir, '"%s" is not a directory' % self.config.path

            if new_root.rev in self._workers:
                return self._workers[new_root.rev]

            new_prefix = self.prefix + '_r' + str(rev)
            filename = new_prefix + '.tar.bz2'
            new_filepath = os.path.join(self.directory, filename)
            if os.path.exists(new_filepath):
                raise IOError('Snapshot file already exists at %s' %
                              new_filepath)

            self._cleanup(self.limit - 1)

            existing = self._get_closest_match(repos, new_root)
            if existing:
                base_rev, base_filepath = existing
                base_root = repos.get_node(self.config.path or '/', base_rev)
                base_prefix = self.prefix + '_r' + str(base_rev)
            else:
                base_root = base_filepath = base_prefix = None

            worker = threading.Thread(target=self._create,
                                      args=(repos, new_root, new_filepath,
                                            new_prefix, base_root,
                                            base_filepath, base_prefix),
                                      name='Create snapshot %s' % filename)
            worker.start()
            self._workers[new_root.rev] = worker
            return worker
        finally:
            self._lock.release()

    def _create(self, repos, new_root, new_filepath, new_prefix, base_root=None,
                base_filepath=None, base_prefix=None):
        """Actually create a snapshot archive.
        
        This is used internally from the C{create()} function and executed in a
        worker thread.
        """
        log.debug('Preparing snapshot archive for %s@%s', new_root.path,
                  new_root.rev)
        if base_root:
            base_rev = repos.next_rev(base_root.rev)
            base_tar = tarfile.open(base_filepath, 'r:bz2')
            base_tar.posix = False
        new_tar = tarfile.open(new_filepath, 'w:bz2')
        new_tar.posix = False

        def _add_entry(node):
            name = node.path[len(self.config.path):]
            if name.startswith('/'):
                name = name[1:]
            new_path = posixpath.join(new_prefix, name)

            # tarfile can't handle unicode
            if isinstance(new_path, unicode):
                new_path = new_path.encode('utf-8')

            if node.isdir:
                log.debug('Adding directory %s/ to archive', name)
                new_info = tarfile.TarInfo(new_path)
                new_info.type = tarfile.DIRTYPE
                new_info.mode = 0755
                new_tar.addfile(new_info)

                for entry in node.get_entries():
                    _add_entry(entry)
                time.sleep(.1) # be nice
            else:
                copy_base = False
                if base_root and repos.has_node(node.path, base_root.rev):
                    base_node = repos.get_node(node.path, base_root.rev)
                    copy_base = base_node.rev == node.rev

                if copy_base:
                    # Copy entry from base archive
                    base_path = posixpath.join(base_prefix, name)
                    base_info = base_tar.getmember(base_path)
                    base_info.name = new_path
                    fileobj = base_tar.extractfile(base_info)
                    new_tar.addfile(base_info, fileobj)
                    fileobj.close()
                    del base_info, fileobj

                else:
                    # Create entry from repository
                    new_info = tarfile.TarInfo(new_path)
                    new_info.type = tarfile.REGTYPE
                    new_info.mtime = node.last_modified
                    if isinstance(new_info.mtime, datetime):
                        new_info.mtime = time.mktime(new_info.mtime.timetuple())
                    new_info.size = node.content_length

                    # FIXME: Subversion specific! This should really be an
                    #        executable flag provided by Trac's versioncontrol
                    #        API
                    if 'svn:executable' in node.get_properties():
                        new_info.mode = 0755
                    else:
                        new_info.mode = 0644

                    new_tar.addfile(new_info, node.get_content())

        try:
            _add_entry(new_root)
        finally:
            new_tar.close()
            if base_root:
                base_tar.close()

        # Create MD5 checksum file
        md5sum.write(new_filepath)

        self._lock.acquire()
        try:
            self._index.append((os.path.getmtime(new_filepath), new_root.rev,
                                new_filepath))
            del self._workers[new_root.rev]
        finally:
            self._lock.release()
        log.info('Prepared snapshot archive at %s', new_filepath)

    def get(self, rev):
        """Returns the path to an already existing snapshot archive for the
        specified revision.
        
        If no snapshot exists for the revision, this function returns C{None}.
        
        @param rev: the repository revision for which a snapshot archive should
            be retrieved
        """
        self._lock.acquire()
        try:
            for mtime, srev, path in self._index:
                if str(rev) == str(srev):
                    return path
            return None
        finally:
            self._lock.release()

    def _get_closest_match(self, repos, root):
        """Determine which existing snapshot archive is closest to the
        requested repository revision."""
        self._lock.acquire()
        try:
            distances = [] # (distance, rev) tuples

            for mtime, srev, path in self._index:
                distance = 0
                srev = repos.normalize_rev(srev)
                get_next = repos.next_rev
                if repos.rev_older_than(root.rev, srev):
                    get_next = repos.previous_rev
                nrev = srev
                while nrev != root.rev:
                    distance += 1
                    nrev = get_next(nrev)
                    if nrev is None:
                        distance = 0
                        break
                if distance:
                    distances.append((distance, srev, path))

            if not distances:
                return None
            distances.sort()
            return distances[0][1:]
        finally:
            self._lock.release()
