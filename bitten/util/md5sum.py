# -*- coding: utf-8 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

"""Convenience functions for creating and validating MD5 checksums for files."""

import md5
import os


class IntegrityError(Exception):
    """Exception raised when checksum validation fails."""


def generate(filename):
    """Generate an MD5 checksum for the specified file.
    
    @param filename: the absolute path to the file
    @return: string containing the checksum
    """
    checksum = md5.new()
    fileobj = file(filename, 'rb')
    try:
        while True:
            chunk = fileobj.read(4096)
            if not chunk:
                break
            checksum.update(chunk)
    finally:
        fileobj.close()
    return checksum.hexdigest()

def write(filename, md5file=None):
    """Write an MD5 checksum file for the specified file.
    
    @param filename: absolute path to the file
    @param md5file: absolute path to the MD5 checksum file to create (optional)
    @return: the absolute path to the created checksum file
    
    If the `md5file` parameter is omitted, this function will write the checksum
    to a file alongside the orignal file, with an added `.md5` extension.
    """
    if md5file is None:
        md5file = filename + '.md5'

    fileobj = file(md5file, 'w')
    try:
        fileobj.write(generate(filename) + '  ' + os.path.basename(filename))
    finally:
        fileobj.close()
    return md5file

def validate(filename, checksum=None):
    """Check the integrity of a specified file against an MD5 checksum.
    
    @param filename: the absolute path to the file
    @param checksum: string containing the checksum (optional)

    If the second parameter is omitted, this function will look for a file with
    an `.md5` extension alongside the original file, and try to read the
    checksum from that file. If no such file is found, an `IntegrityError` is
    raised.

    If the file does not match the checksum, an `IntegrityError` is raised.
    """
    if checksum is None:
        md5file = filename + '.md5'
        if not os.path.isfile(md5file):
            md5file = os.path.splitext(filename)[0] + '.md5'
            if not os.path.isfile(md5file):
                raise IntegrityError('Checksum file not found')
        fileobj = file(md5file, 'r')
        try:
            content = fileobj.read()
        finally:
            fileobj.close()
        try:
            checksum, path = content.split('  ')
        except ValueError:
            raise IntegrityError('Checksum file invalid')
        if path != os.path.basename(filename):
            raise IntegrityError('Checksum for a different file')

    expected = generate(filename)
    if expected != checksum:
        raise IntegrityError('Checksum does not match')
