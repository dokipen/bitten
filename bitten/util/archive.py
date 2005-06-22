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

import os.path
import time

_formats = {'gzip': ('.tar.gz', 'gz'), 'bzip2': ('.tar.bz2', 'bz2'),
            'zip': ('.zip', None)}

def make_archive(env, path=None, rev=None, format='gzip'):
    repos = env.get_repository()
    root = repos.get_node(path or '/', rev)
    if not root.isdir:
        raise Exception, '"%s" is not a directory' % path

    assert format in _formats, 'Unknown archive format: %s' % format

    filedir = os.path.join(env.path, 'snapshots')
    if not os.access(filedir, os.R_OK + os.W_OK):
        raise IOError, 'Insufficient permissions to create tarball'
    prefix = '%s_r%s' % (root.path.replace('/', '-'), root.rev)
    filename = os.path.join(filedir, prefix + _formats[format][0])

    if format in ('bzip2', 'gzip'):
        _make_tar_archive(env, root, filename, prefix, format)
    else:
        _make_zip_archive(env, root, filename, prefix)

def _make_tar_archive(env, root, filename, prefix, format):
    import tarfile
    tar = tarfile.open(filename, 'w:' + _formats[format][1])

    def _add_entry(prefix, node):
        name = node.path[len(root.path):]
        if name.startswith('/'):
            name = name[1:]
        if node.isdir:
            for entry in node.get_entries():
                _add_entry(os.path.join(prefix, name), entry)
        else:
            info = tarfile.TarInfo(os.path.join(prefix, name))
            info.type = tarfile.REGTYPE
            info.mtime = node.last_modified
            info.size = node.content_length
            tar.addfile(info, node.get_content())
    _add_entry(prefix, root)

    tar.close()

def _make_zip_archive(env, root, filename, prefix):
    import zipfile
    zip = zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED)

    def _add_entry(prefix, node):
        name = node.path[len(root.path):]
        if name.startswith('/'):
            name = name[1:]
        if node.isdir:
            for entry in node.get_entries():
                _add_entry(os.path.join(prefix, name), entry)
        else:
            info = zipfile.ZipInfo(os.path.join(prefix, name))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.date_time = time.gmtime(node.last_modified)[:6]
            info.file_size = node.content_length
            zip.writestr(info, node.get_content().read())
    _add_entry(prefix, root)

    zip.close()
