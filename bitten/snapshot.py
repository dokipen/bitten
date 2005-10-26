# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

"""Snapshot archive management.

Snapshots of the code base are stored in the Trac environment as ZIP files.

These files use the naming convention `[config_name]_r[revision].zip` so they
can be located programmatically after creation, and associated with the build
config and revision they apply to.

These snapshot files are accompanied by a checksum file (using MD5). Any archive
file with no accompanying checksum is considered incomplete or invalid.

For larger code bases, these snapshots may be relatively expensive to create.
Most of the time is spent in walking the repository directory and reading the
files it contains. To avoid blocking the build master while snapshots are
created, this is done in a worker thread. The main thread polls the snapshots
directory to find the snapshots that have been completely created (including
the corresponding checksum file).

As snapshot archives are often very similar to each other for subsequent
revisions, an attempt is made to avoid the creation of new archives from
scratch. Instead, the build master keeps the most recently used archives (MRU
cache) and will build new archives based on the deltas provided by the version
control system. Using the nearest existing snapshot as the base, deleted files
and directories are removed from the snapshot, added files/directories are
added, and modified files are updated.
"""

import logging
import os
try:
    import threading
except ImportError:
    import dummy_threading as threading
import time
import zipfile

from bitten.util import md5sum

log = logging.getLogger('bitten.snapshot')

MAX_SNAPSHOTS = 10
SNAPSHOTS_DIR = 'snapshots'


class SnapshotManager(object):
    """Manages snapshot archives for a specific build configuration."""

    def __init__(self, config):
        """Create the snapshot manager.
        
        @param config: The `BuildConfig` instance
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
            raise IOError, 'Insufficient permissions to create snapshots in ' \
                           + self.directory

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
            if not filename.endswith('.zip'):
                continue
            rest = filename[len(self.prefix):-4]
            if not rest.startswith('_r'):
                continue
            rev = rest[2:]

            filepath = os.path.join(self.directory, filename)
            try:
                md5sum.validate(filepath)
            except md5sum.IntegrityError, e:
                log.warning('Integrity error checking %s (e)', filepath, e)
                continue
            mtime = os.path.getmtime(filepath)

            yield mtime, rev, filepath

    def _cleanup(self, limit=None):
        """Remove obsolete snapshots to preserve disk space."""
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
        """
        self._lock.acquire()
        try:
            repos = self.env.get_repository()
            root = repos.get_node(self.config.path or '/', rev)
            assert root.isdir, '"%s" is not a directory' % self.config.path

            if root.rev in self._workers:
                return self._workers[root.rev]

            prefix = self.prefix + '_r' + str(rev)
            filename = prefix + '.zip'
            filepath = os.path.join(self.directory, filename)
            if os.path.exists(filepath):
                raise IOError, 'Snapshot file already exists at %s' % filepath

            self._cleanup(self.limit - 1)

            worker = threading.Thread(target=self._create,
                                      args=(prefix, root, filepath),
                                      name='Create snapshot %s' % filename)
            worker.start()
            self._workers[root.rev] = worker
            return worker
        finally:
            self._lock.release()

    def _create(self, prefix, root, filepath):
        """Actually create a snapshot archive.
        
        This is used internally from the `create()` function and executed in a
        worker thread.
        """
        log.debug('Preparing snapshot archive for %s@%s', root.path, root.rev)

        zip_file = zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED)
        def _add_entry(node):
            name = node.path[len(self.config.path):]
            if name.startswith('/'):
                name = name[1:]
            if node.isdir:
                path = os.path.join(prefix, name).rstrip('/\\') + '/'
                info = zipfile.ZipInfo(path)
                info.create_system = 3
                info.external_attr = 040755 << 16L | 0x10
                zip_file.writestr(info, '')
                log.debug('Adding directory %s to archive', name)
                for entry in node.get_entries():
                    _add_entry(entry)
                time.sleep(.1) # be nice
            else:
                path = os.path.join(prefix, name)
                info = zipfile.ZipInfo(path)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                info.date_time = time.gmtime(node.last_modified)[:6]
                info.file_size = node.content_length

                # FIXME: Subversion specific! This should really be an
                #        executable flag provided by Trac's versioncontrol API
                if 'svn:executable' in node.get_properties():
                    info.external_attr = 0100755 << 16L
                else:
                    info.external_attr = 0100644 << 16L

                zip_file.writestr(info, node.get_content().read())
        try:
            _add_entry(root)
        finally:
            zip_file.close()

        # Create MD5 checksum file
        md5sum.write(filepath)

        self._lock.acquire()
        try:
            self._index.append((os.path.getmtime(filepath), root.rev, filepath))
            del self._workers[root.rev]
        finally:
            self._lock.release()
        log.info('Prepared snapshot archive at %s', filepath)

    def get(self, rev):
        """Returns the path to an already existing snapshot archive for the
        specified revision.
        
        If no snapshot exists for the revision, this function returns `None`.
        """
        self._lock.acquire()
        try:
            for mtime, srev, path in self._index:
                if str(rev) == str(srev):
                    return path
            return None
        finally:
            self._lock.release()
