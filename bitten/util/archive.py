# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
#
# Bitten is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#
# Trac is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#
# Author: Christopher Lenz <cmlenz@gmx.de>

import logging
import os.path
import tarfile
import time
import zipfile

_formats = {'gzip': ('.tar.gz', 'gz'), 'bzip2': ('.tar.bz2', 'bz2'),
            'zip': ('.zip', None)}

def pack(env, repos=None, path=None, rev=None, prefix=None, format='gzip'):
    if repos is None:
        repos = env.get_repository()
    root = repos.get_node(path or '/', rev)
    if not root.isdir:
        raise Exception, '"%s" is not a directory' % path

    assert format in _formats, 'Unknown archive format: %s' % format

    filedir = os.path.join(env.path, 'snapshots')
    if not os.access(filedir, os.R_OK + os.W_OK):
        raise IOError, 'Insufficient permissions to create tarball'
    if not prefix:
        prefix = root.path.replace('/', '-')
    prefix += '_r%s' % root.rev
    filename = os.path.join(filedir, prefix + _formats[format][0])

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
            info = tarfile.TarInfo(os.path.join(prefix, name))
            info.type = tarfile.REGTYPE
            info.mtime = node.last_modified
            info.size = node.content_length
            archive.addfile(info, node.get_content())
        else: # ZIP format
            info = zipfile.ZipInfo(os.path.join(prefix, name))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.date_time = time.gmtime(node.last_modified)[:6]
            info.file_size = node.content_length
            archive.writestr(info, node.get_content().read())
    _add_entry(root)

    archive.close()

    return filename

def unpack(filename, dest_path, format=None):
    if not format:
        for name, (extension, compression) in _formats.items():
            if filename.endswith(extension):
                format = name
                break
        if not format:
            raise Exception, 'Unkown archive extension: %s' \
                             % os.path.splitext(filename)[1]

    names = []
    if format in ('bzip2', 'gzip'):
        tar = tarfile.open(filename)
        for tarinfo in tar:
            names.append(tarinfo.name)
            tar.extract(tarinfo, dest_path)
    elif format == 'zip':
        zip = zipfile.ZipFile(filename, 'r')
        for name in zip.namelist():
            names.append(name)
            if name.endswith('/'):
                os.makedirs(os.path.join(path, name))
            else:
                file(os.path.join(path, name), 'wb').write(zip.read(name))
    return os.path.commonprefix(names)
