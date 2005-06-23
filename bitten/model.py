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

schema_version = 1


class Configuration(object):
    """Representation of a build configuration."""

    _table = Table('bitten_config', key='name')[
        Column('name'), Column('path'), Column('label'),
        Column('active', type='int'), Column('description')
    ]

    def __init__(self, env, name=None, db=None):
        self.env = env
        self.name = self._old_name = None
        self.path = self.label = self.description = self.active = None
        if name:
            self._fetch(name, db)

    exists = property(fget=lambda self: self._old_name is not None)

    def _fetch(self, name, db=None):
        if not db:
            db = self.env.get_db_cnx()

        cursor = db.cursor()
        cursor.execute("SELECT path,label,active,description FROM bitten_config "
                       "WHERE name=%s", (name,))
        row = cursor.fetchone()
        if not row:
            raise Exception, "Build configuration %s does not exist" % name
        self.name = self._old_name = name
        self.path = row[0] or ''
        self.label = row[1] or ''
        self.active = row[2] and True or False
        self.description = row[3] or ''

    def insert(self, db=None):
        assert not self.exists, 'Cannot insert existing configuration'
        assert self.name, 'Configuration requires a name'
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        cursor = db.cursor()
        cursor.execute("INSERT INTO bitten_config "
                       "(name,path,label,active,description) "
                       "VALUES (%s,%s,%s,%s,%s)",
                       (self.name, self.path, self.label, int(self.active or 0),
                        self.description))

        if handle_ta:
            db.commit()

    def update(self, db=None):
        assert self.exists, 'Cannot update a non-existing configuration'
        assert self.name, 'Configuration requires a name'
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        cursor = db.cursor()
        cursor.execute("UPDATE bitten_config SET name=%s,path=%s,label=%s,"
                       "active=%s,description=%s WHERE name=%s",
                       (self.name, self.path, self.label, int(self.active or 0),
                        self.description, self._old_name))

        if handle_ta:
            db.commit()

    def select(cls, env, include_inactive=False, db=None):
        if not db:
            db = env.get_db_cnx()
        where = ''
        cursor = db.cursor()
        if include_inactive:
            cursor.execute("SELECT name,path,label,active,description "
                           "FROM bitten_config ORDER BY name")
        else:
            cursor.execute("SELECT name,path,label,active,description "
                           "FROM bitten_config WHERE active=1 "
                           "ORDER BY name")
        for name, path, label, active, description in cursor:
            config = Configuration(env)
            config.name = name
            config.path = path or ''
            config.label = label or ''
            config.active = active and True or False
            config.description = description or ''
            yield config
    select = classmethod(select)


class Build(object):
    """Representation of a build."""

    _table = Table('bitten_build', key=('path', 'rev', 'slave'))[
        Column('rev'), Column('path'), Column('slave'),
        Column('time', type='int'), Column('duration', type='int'),
        Column('status', type='int')
    ]

    FAILURE = 'failure'
    IN_PROGRESS = 'in-progress'
    SUCCESS = 'success'

    def __init__(self, env, path=None, rev=None, slave=None, db=None):
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
        self.rev = rev
        self.path = path
        self.slave = slave
        self.time = row[0] and int(row[0])
        self.duration = row[1] and int(row[1])
        if row[2] is not None:
            self.status = row[2] and Build.SUCCESS or Build.FAILURE
        else:
            self.status = Build.IN_PROGRESS

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

    def select(cls, env, path=None, rev=None, slave=None, db=None):
        if not db:
            db = env.get_db_cnx()

        where_clauses = []
        if rev is not None:
            where_clauses.append(("rev=%s", rev))
        if path is not None:
            where_clauses.append(("path=%s", path))
        if slave is not None:
            where_clauses.append(("slave=%s", path))
        if where_clauses:
            where = "WHERE " + " AND ".join([wc[0] for wc in where_clauses])
        else:
            where = ""

        cursor = db.cursor()
        cursor.execute("SELECT rev,path,slave,time,duration,status "
                       "FROM bitten_build " + where,
                       [wc[1] for wc in where_clauses])
        for rev, path, slave, time, duration, status in cursor:
            build = Build(env)
            build.rev = rev
            build.path = path
            build.slave = slave
            build.time = time and int(time)
            build.duration = duration and int(duration)
            if status is not None:
                build.status = status and Build.SUCCESS or Build.FAILURE
            else:
                build.status = Build.FAILURE
            yield build
    select = classmethod(select)
