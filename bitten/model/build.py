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

from trac.db_default import Table, Column


class Build(object):
    """Representation of a build."""

    _table = Table('bitten_build', key=('rev', 'path', 'slave'))[
        Column('rev'), Column('path'), Column('slave'),
        Column('time', type='int'), Column('duration', type='int'),
        Column('status', type='int')
    ]

    FAILURE = 'failure'
    IN_PROGRESS = 'in-progress'
    SUCCESS = 'success'

    def __init__(self, env, rev=None, path=None, slave=None, db=None):
        self.env = env
        self.rev = self.path = self.slave = None
        self.time = self.duration = self.status = None
        if rev:
            self._fetch(rev, path, slave, db)

    def _fetch(self, rev, path, slave, db=None):
        if not db:
            db = self.env.get_db_cnx()

        cursor = db.cursor()
        cursor.execute("SELECT time,duration,status FROM bitten_build "
                       "WHERE rev=%s AND path=%s AND slave=%s",
                       (rev, path, slave))
        row = cursor.fetchone()
        if not row:
            raise Exception, "Build not found"
        self.time = row[0] and int(row[0])
        self.duration = row[1] and int(row[1])
        if row[2] is not None:
            self.status = row[2] and Build.SUCCESS or Build.FAILURE
        else:
            self.status = Build.FAILURE

    completed = property(fget=lambda self: self.status != Build.IN_PROGRESS)
    successful = property(fget=lambda self: self.status == Build.SUCCESS)

    def insert(self, db=None):
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        cursor = db.cursor()
        cursor.execute("INSERT INTO bitten_build VALUES (%s,%s,%s,%s,%s,%s)",
                       (self.rev, self.path, self.slave, self.time,
                        self.duration, self.status or Build.IN_PROGRESS))
