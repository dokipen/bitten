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

from trac.db_default import Table, Column, Index


class BuildConfig(object):
    """Representation of a build configuration."""

    _schema = [
        Table('bitten_config', key='name')[
            Column('name'), Column('path'), Column('label'),
            Column('active', type='int'), Column('description')
        ]
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


class TargetPlatform(object):
    """Target platform for a build configuration."""

    _schema = [
        Table('bitten_platform', key='id')[
            Column('id', auto_increment=True), Column('config'), Column('name')
        ],
        Table('bitten_rule', key=('id', 'propname'))[
            Column('id'), Column('propname'), Column('pattern'),
            Column('orderno', type='int')
        ]
    ]

    def __init__(self, env, id=None, db=None):
        self.env = env
        self.rules = []
        if id is not None:
            self._fetch(id, db)
        else:
            self.id = self.config = self.name = None

    def _fetch(self, id, db=None):
        if not db:
            db = self.env.get_db_cnx()

        cursor = db.cursor()
        cursor.execute("SELECT config,name FROM bitten_platform "
                       "WHERE id=%s", (id,))
        row = cursor.fetchone()
        if not row:
            raise Exception, 'Target platform %s does not exist' % id
        self.id = id
        self.config = row[0]
        self.name = row[1]

        cursor.execute("SELECT propname,pattern FROM bitten_rule "
                       "WHERE id=%s ORDER BY orderno", (id,))
        for propname, pattern in cursor:
            self.rules.append((propname, pattern))

    exists = property(fget=lambda self: self.id is not None)

    def insert(self, db=None):
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        assert not self.exists, 'Cannot insert existing target platform'
        assert self.config, 'Target platform needs to be associated with a ' \
                            'configuration'
        assert self.name, 'Target platform requires a name'

        cursor = db.cursor()
        cursor.execute("INSERT INTO bitten_platform (config,name) "
                       "VALUES (%s,%s)", (self.config, self.name))
        self.id = db.get_last_id('bitten_platform')
        cursor.executemany("INSERT INTO bitten_rule VALUES (%s,%s,%s,%s)",
                           [(self.id, propname, pattern, idx) for
                            idx, (propname, pattern) in enumerate(self.rules)])

        if handle_ta:
            db.commit()

    def update(self, db=None):
        assert self.exists, 'Cannot update a non-existing platform'
        assert self.config, 'Target platform needs to be associated with a ' \
                            'configuration'
        assert self.name, 'Target platform requires a name'
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        cursor = db.cursor()
        cursor.execute("UPDATE bitten_platform SET name=%s WHERE id=%s",
                       (self.name, self.id))
        cursor.execute("DELETE FROM bitten_rule WHERE id=%s", (self.id))
        cursor.executemany("INSERT INTO bitten_rule VALUES (%s,%s,%s,%s)",
                           [(self.id, propname, pattern, idx) for
                            idx, (propname, pattern) in enumerate(self.rules)])

        if handle_ta:
            db.commit()

    def select(cls, env, config=None, db=None):
        if not db:
            db = env.get_db_cnx()

        where_clauses = []
        if config is not None:
            where_clauses.append(("config=%s", config))
        if where_clauses:
            where = "WHERE " + " AND ".join([wc[0] for wc in where_clauses])
        else:
            where = ""

        cursor = db.cursor()
        cursor.execute("SELECT id FROM bitten_platform %s ORDER BY name"
                       % where, [wc[1] for wc in where_clauses])
        for (id,) in cursor:
            yield TargetPlatform(env, id)
    select = classmethod(select)


class Build(object):
    """Representation of a build."""

    _schema = [
        Table('bitten_build', key='id')[
            Column('id', auto_increment=True), Column('config'), Column('rev'),
            Column('rev_time', type='int'), Column('slave'),
            Column('started', type='int'), Column('stopped', type='int'),
            Column('status', size='1'),  Index(['config', 'rev', 'slave'])
        ],
        Table('bitten_slave', key=('build', 'propname'))[
            Column('build', type='int'), Column('propname'), Column('propvalue')
        ]
    ]

    # Build status codes
    PENDING = 'P'
    IN_PROGRESS = 'I'
    SUCCESS = 'S'
    FAILURE = 'F'

    # Standard slave properties
    IP_ADDRESS = 'ipnr'
    MAINTAINER = 'owner'
    OS_NAME = 'os'
    OS_FAMILY = 'family'
    OS_VERSION = 'version'
    MACHINE = 'machine'
    PROCESSOR = 'processor'

    def __init__(self, env, id=None, db=None):
        self.env = env
        self.slave_info = {}
        if id is not None:
            self._fetch(id, db)
        else:
            self.id = self.config = self.rev = self.slave = None
            self.started = self.stopped = self.rev_time = 0
            self.status = self.PENDING

    def _fetch(self, id, db=None):
        if not db:
            db = self.env.get_db_cnx()

        cursor = db.cursor()
        cursor.execute("SELECT config,rev,rev_time,slave,started,stopped,"
                       "status FROM bitten_build WHERE id=%s", (id,))
        row = cursor.fetchone()
        if not row:
            raise Exception, "Build %s not found" % id
        self.id = id
        self.config = row[0]
        self.rev = row[1]
        self.rev_time = int(row[2])
        self.slave = row[3]
        self.started = row[4] and int(row[4])
        self.stopped = row[5] and int(row[5])
        self.status = row[6]

        cursor.execute("SELECT propname,propvalue FROM bitten_slave "
                       "WHERE build=%s", (self.id,))
        for propname, propvalue in cursor:
            self.slave_info[propname] = propvalue

    exists = property(fget=lambda self: self.id is not None)
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
        cursor.execute("DELETE FROM bitten_build WHERE id=%s", (self.id,))
        if handle_ta:
            db.commit()

    def insert(self, db=None):
        if not db:
            db = self.env.get_db_cnx()
            handle_ta = True
        else:
            handle_ta = False

        assert self.config and self.rev and self.rev_time
        assert self.status in (self.PENDING, self.IN_PROGRESS, self.SUCCESS,
                               self.FAILURE)
        if not self.slave:
            assert self.status == self.PENDING

        cursor = db.cursor()
        cursor.execute("INSERT INTO bitten_build (config,rev,rev_time,slave,"
                       "started,stopped,status) "
                       "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                       (self.config, self.rev, self.rev_time, self.slave or '',
                        self.started or 0, self.stopped or 0, self.status))
        self.id = db.get_last_id('bitten_build')
        cursor.executemany("INSERT INTO bitten_slave VALUES (%s,%s,%s)",
                           [(self.id, name, value) for name, value
                            in self.slave_info.items()])

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
        cursor.execute("UPDATE bitten_build SET slave=%s,started=%s,"
                       "stopped=%s,status=%s WHERE id=%s",
                       (self.slave or '', self.started or 0,
                        self.stopped or 0, self.status, self.id))
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
        cursor.execute("SELECT id,config,rev,slave,started,stopped,status,"
                       "rev_time FROM bitten_build %s "
                       "ORDER BY config,rev_time DESC,slave"
                       % where, [wc[1] for wc in where_clauses])
        for id, config, rev, slave, started, stopped, status, rev_time \
                in cursor:
            build = Build(env)
            build.id = id
            build.config = config
            build.rev = rev
            build.slave = slave
            build.started = started and int(started) or 0
            build.stopped = stopped and int(stopped) or 0
            build.status = status
            build.rev_time = int(rev_time)
            yield build
    select = classmethod(select)


schema = BuildConfig._schema + TargetPlatform._schema + Build._schema
schema_version = 1
