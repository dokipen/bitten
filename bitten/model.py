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


class BuildConfig(object):
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
                       (self.name, self.path, self.label or '',
                        int(self.active or 0), self.description or ''))

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
            config = BuildConfig(env)
            config.name = name
            config.path = path or ''
            config.label = label or ''
            config.active = active and True or False
            config.description = description or ''
            yield config
    select = classmethod(select)


class Build(object):
    """Representation of a build."""

    _table = Table('bitten_build', key=('config', 'rev', 'slave'))[
        Column('config'), Column('rev'), Column('slave'),
        Column('time', type='int'), Column('duration', type='int'),
        Column('status', size='1')
    ]

    PENDING = 'P'
    IN_PROGRESS = 'I'
    SUCCESS = 'S'
    FAILURE = 'F'

    def __init__(self, env, config=None, rev=None, slave=None, db=None):
        self.env = env
        self.config = self.rev = self.slave = self.time = self.duration = None
        if config and rev and slave:
            self._fetch(config, rev, slave, db)
        else:
            self.time = self.duration = 0
            self.status = self.PENDING

    def _fetch(self, config, rev, slave, db=None):
        if not db:
            db = self.env.get_db_cnx()

        cursor = db.cursor()
        cursor.execute("SELECT time,duration,status FROM bitten_build "
                       "WHERE config=%s AND rev=%s AND slave=%s",
                       (config, rev, slave))
        row = cursor.fetchone()
        if not row:
            raise Exception, "Build not found"
        self.config = config
        self.rev = rev
        self.slave = slave
        self.time = row[0] and int(row[0])
        self.duration = row[1] and int(row[1])
        self.status = row[2]

    completed = property(fget=lambda self: self.status != Build.IN_PROGRESS)
    successful = property(fget=lambda self: self.status == Build.SUCCESS)

    def delete(self, db=None):
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        assert self.status == self.PENDING, 'Only pending builds can be deleted'

        cursor = db.cursor()
        cursor.execute("DELETE FROM bitten_build WHERE config=%s AND rev=%s "
                       "AND slave=%s", (self.config, self.rev,
                       self.slave or ''))
        if handle_ta:
            db.commit()

    def insert(self, db=None):
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        assert self.config and self.rev
        assert self.status in (self.PENDING, self.IN_PROGRESS, self.SUCCESS,
                               self.FAILURE)
        if not self.slave:
            assert self.status == self.PENDING

        cursor = db.cursor()
        cursor.execute("INSERT INTO bitten_build VALUES (%s,%s,%s,%s,%s,%s)",
                       (self.config, self.rev, self.slave or '', self.time or 0,
                        self.duration or 0, self.status))
        if handle_ta:
            db.commit()

    def update(self, db=None):
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        assert self.config and self.rev
        assert self.status in (self.PENDING, self.IN_PROGRESS, self.SUCCESS,
                               self.FAILURE)
        if not self.slave:
            assert self.status == self.PENDING

        cursor = db.cursor()
        cursor.execute("UPDATE bitten_build SET slave=%s,time=%s,duration=%s,"
                       "status=%s WHERE config=%s AND rev=%s",
                       (self.slave or '', self.time or 0, self.duration or 0,
                        self.status, self.config, self.rev))
        if handle_ta:
            db.commit()

    def select(cls, env, config=None, rev=None, slave=None, status=None,
               db=None):
        if not db:
            db = env.get_db_cnx()

        where_clauses = []
        if config is not None:
            where_clauses.append(("config=%s", config))
        if rev is not None:
            where_clauses.append(("rev=%s", rev))
        if slave is not None:
            where_clauses.append(("slave=%s", slave))
        if status is not None:
            where_clauses.append(("status=%s", status))
        if where_clauses:
            where = "WHERE " + " AND ".join([wc[0] for wc in where_clauses])
        else:
            where = ""

        cursor = db.cursor()
        cursor.execute("SELECT config,rev,slave,time,duration,status "
                       "FROM bitten_build %s ORDER BY config,rev,slave" % where,
                       [wc[1] for wc in where_clauses])
        for config, rev, slave, time, duration, status in cursor:
            build = Build(env)
            build.config = config
            build.rev = rev
            build.slave = slave
            build.time = time and int(time) or 0
            build.duration = duration and int(duration) or 0
            build.status = status
            yield build
    select = classmethod(select)
