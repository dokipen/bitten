# -*- coding: utf-8 -*-
#
# Copyright (C) 2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

"""Recipe commands for Subversion."""

import logging
import posixpath

log = logging.getLogger('bitten.build.svntools')

__docformat__ = 'restructuredtext en'

def checkout(ctxt, url, path=None, revision=None, dir_='.'):
    """Perform a checkout from a Subversion repository.
    
    :param ctxt: the build context
    :type ctxt: `Context`
    :param url: the URL of the repository
    :param path: the path inside the repository
    :param revision: the revision to check out
    :param dir_: the name of a local subdirectory to check out into
    """
    args = ['checkout']
    if revision:
        args += ['-r', revision]
    if path:
        url = posixpath.join(url, path)
    args += [url, dir_]

    from bitten.build import shtools
    returncode = shtools.execute(ctxt, file_='svn', args=args)
    if returncode != 0:
        ctxt.error('svn checkout failed (%s)' % returncode)

def export(ctxt, url, path=None, revision=None, dir_='.'):
    """Perform an export from a Subversion repository.
    
    :param ctxt: the build context
    :type ctxt: `Context`
    :param url: the URL of the repository
    :param path: the path inside the repository
    :param revision: the revision to check out
    :param dir_: the name of a local subdirectory to export out into
    """
    args = ['export', '--force']
    if revision:
        args += ['-r', revision]
    if path:
        url = posixpath.join(url, path)
    args += [url, dir_]

    from bitten.build import shtools
    returncode = shtools.execute(ctxt, file_='svn', args=args)
    if returncode != 0:
        ctxt.error('svn export failed (%s)' % returncode)

def update(ctxt, revision=None, dir_='.'):
    """Update the local working copy from the Subversion repository.
    
    :param ctxt: the build context
    :type ctxt: `Context`
    :param revision: the revision to check out
    :param dir_: the name of a local subdirectory containing the working copy
    """
    args = ['update']
    if revision:
        args += ['-r', revision]
    args += [dir_]

    from bitten.build import shtools
    returncode = shtools.execute(ctxt, file_='svn', args=args)
    if returncode != 0:
        ctxt.error('svn update failed (%s)' % returncode)
