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

from trac.core import *
from trac.env import IEnvironmentSetupParticipant
from trac.perm import IPermissionRequestor
from trac.wiki import IWikiSyntaxProvider
from bitten.model import schema, schema_version, Build, BuildConfig


class BuildSystem(Component):

    implements(IEnvironmentSetupParticipant, IPermissionRequestor,
               IWikiSyntaxProvider)

    # IEnvironmentSetupParticipant methods

    def environment_created(self):
        # Create the required tables
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        for table in schema:
            for stmt in db.to_sql(table):
                cursor.execute(stmt)

        # Insert a global version flag
        cursor.execute("INSERT INTO system (name,value) "
                       "VALUES ('bitten_version',%s)", (schema_version,))

        # Create the directory for storing snapshot archives
        tarballs_dir = os.path.join(self.env.path, 'snapshots')

        db.commit()

    def environment_needs_upgrade(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT value FROM system WHERE name='bitten_version'")
        row = cursor.fetchone()
        self.log.debug("Current DB version is %s, we need %s",
                       row and int(row[0]) or None, schema_version)
        if not row or int(row[0]) < schema_version:
            return True

    def upgrade_environment(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT value FROM system WHERE name='bitten_version'")
        row = cursor.fetchone()
        if not row:
            self.environment_created()
        else:
            current_version = int(row[0])
            from bitten import upgrades
            for version in range(current_version + 1, schema_version + 1):
                self.log.debug('Updating to schema version %s', version)
                for function in upgrades.map.get(version):
                    self.log.debug('Executing upgrade function %s', function)
                    function(self.env, db)
            cursor.execute("UPDATE system SET value=%s WHERE "
                           "name='bitten_version'", (schema_version,))
            self.log.info('Upgraded Bitten tables from version %d to %d',
                          current_version, schema_version)

    # IPermissionRequestor methods

    def get_permission_actions(self):
        actions = ['BUILD_VIEW', 'BUILD_CREATE', 'BUILD_MODIFY', 'BUILD_DELETE']
        return actions + [('BUILD_ADMIN', actions)]

    # IWikiSyntaxProvider methods

    def get_wiki_syntax(self):
        return []

    def get_link_resolvers(self):
        def _format_link(formatter, ns, name, label):
            build = Build.fetch(self.env, int(name))
            if build:
                config = BuildConfig.fetch(self.env, build.config)
                title = 'Build %d ([%s] of %s) by %s' % (build.id, build.rev,
                        config.label, build.slave)
                return '<a class="build" href="%s" title="%s">%s</a>' \
                       % (formatter.href.build(build.config, build.id), title,
                          label)
            return label
        yield 'build', _format_link
