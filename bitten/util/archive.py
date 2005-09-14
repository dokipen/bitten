# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import os
import tarfile
import time
import zipfile

_formats = {'gzip': ('.tar.gz', 'gz'), 'bzip2': ('.tar.bz2', 'bz2'),
            'zip': ('.zip', None)}

class Error(Exception):
    """Error raised when packing or unpacking a snapshot archive fails."""

def index(env, prefix):
    """Generator that yields `(rev, format, path)` tuples for every archive in
    the environment snapshots directory that match the specified prefix.
    """
    filedir = os.path.join(env.path, 'snapshots')
    for filename in [f for f in os.listdir(filedir) if f.startswith(prefix)]:
        rest = filename[len(prefix):]

        # Determine format based of file extension
        format = None
        for name, (extension, _) in _formats.items():
            if rest.endswith(extension):
                rest = rest[:-len(extension)]
                format = name
        if not format:
            continue

        if not rest.startswith('_r'):
            continue
        rev = rest[2:]

        yield rev, format, os.path.join(filedir, filename)

def pack(env, repos=None, path=None, rev=None, prefix=None, format='gzip',
         overwrite=False):
    """Create a snapshot archive in the specified format."""
    if repos is None:
        repos = env.get_repository()
    root = repos.get_node(path or '/', rev)
    if not root.isdir:
        raise Error, '"%s" is not a directory' % path

    if format not in _formats:
        raise Error, 'Unknown archive format: %s' % format

    filedir = os.path.join(env.path, 'snapshots')
    if not os.access(filedir, os.R_OK + os.W_OK):
        raise Error, 'Insufficient permissions to create tarball'
    if not prefix:
        prefix = root.path.replace('/', '-')
    prefix += '_r%s' % root.rev
    filename = os.path.join(filedir, prefix + _formats[format][0])

    if not overwrite and os.path.isfile(filename):
        return filename

    if format in ('bzip2', 'gzip'):
        archive = tarfile.open(filename, 'w:' + _formats[format][1])
    else:
        archive = zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED)

    def _add_entry(node):
        name = node.path[len(root.path):]
        if name.startswith('/'):
            name = name[1:]
        if node.isdir:
            for entry in node.get_entries():
                _add_entry(entry)
        elif format in ('bzip2', 'gzip'):
            try:
                info = tarfile.TarInfo(os.path.join(prefix, name))
                info.type = tarfile.REGTYPE
                info.mtime = node.last_modified
                info.size = node.content_length
                archive.addfile(info, node.get_content())
            except tarfile.TarError, e:
                raise Error, e
        else: # ZIP format
            try:
                info = zipfile.ZipInfo(os.path.join(prefix, name))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.date_time = time.gmtime(node.last_modified)[:6]
                info.file_size = node.content_length
                archive.writestr(info, node.get_content().read())
            except zipfile.error, e:
                raise Error, e
    _add_entry(root)

    archive.close()

    return filename

def unpack(filename, dest_path, format=None):
    """Extract the contents of a snapshot archive."""
    if not format:
        for name, (extension, _) in _formats.items():
            if filename.endswith(extension):
                format = name
                break
        if not format:
            raise Error, 'Unkown archive extension: %s' \
                         % os.path.splitext(filename)[1]

    names = []
    if format in ('bzip2', 'gzip'):
        try:
            tar_file = tarfile.open(filename)
            for tarinfo in tar_file:
                names.append(tarinfo.name)
                tar_file.extract(tarinfo, dest_path)
        except tarfile.TarError, e:
            raise Error, e
    elif format == 'zip':
        try:
            zip_file = zipfile.ZipFile(filename, 'r')
            for name in zip_file.namelist():
                names.append(name)
                path = os.path.join(dest_path, name)
                if name.endswith('/'):
                    os.makedirs(path)
                else:
                    file(path, 'wb').write(zip_file.read(name))
        except zipfile.error:
            raise Error, e
    return os.path.commonprefix(names)
