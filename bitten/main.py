# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import inspect
import os
import textwrap

from trac.attachment import ILegacyAttachmentPolicyDelegate
from trac.core import *
from trac.db import DatabaseManager
from trac.env import IEnvironmentSetupParticipant
from trac.perm import IPermissionRequestor
from trac.resource import IResourceManager
from trac.wiki import IWikiSyntaxProvider
from bitten.api import IBuildListener
from bitten.model import schema, schema_version, Build, BuildConfig

__all__ = ['BuildSystem']
__docformat__ = 'restructuredtext en'


class BuildSetup(Component):

    implements(IEnvironmentSetupParticipant)

    # IEnvironmentSetupParticipant methods

    def environment_created(self):
        # Create the required tables
        db = self.env.get_db_cnx()
        connector, _ = DatabaseManager(self.env)._get_connector()
        cursor = db.cursor()
        for table in schema:
            for stmt in connector.to_sql(table):
                cursor.execute(stmt)

        # Insert a global version flag
        cursor.execute("INSERT INTO system (name,value) "
                       "VALUES ('bitten_version',%s)", (schema_version,))

        # Create the directory for storing snapshot archives
        snapshots_dir = os.path.join(self.env.path, 'snapshots')
        os.mkdir(snapshots_dir)

        db.commit()

    def environment_needs_upgrade(self, db):
        cursor = db.cursor()
        cursor.execute("SELECT value FROM system WHERE name='bitten_version'")
        row = cursor.fetchone()
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
                for function in upgrades.map.get(version):
                    print textwrap.fill(inspect.getdoc(function))
                    function(self.env, db)
                    cursor.execute("UPDATE system SET value=%s WHERE "
                           "name='bitten_version'", (version,))
                db.commit()
                print "Bitten upgrade to version %d done." % version
                self.log.info('Upgraded Bitten tables to version %d',
                                version)

class BuildSystem(Component):

    implements(IPermissionRequestor,
               IWikiSyntaxProvider, IResourceManager,
               ILegacyAttachmentPolicyDelegate)

    listeners = ExtensionPoint(IBuildListener)

    # IPermissionRequestor methods

    def get_permission_actions(self):
        actions = ['BUILD_VIEW', 'BUILD_CREATE', 'BUILD_MODIFY', 'BUILD_DELETE',
                   'BUILD_EXEC']
        return actions + [('BUILD_ADMIN', actions)]

    # IWikiSyntaxProvider methods

    def get_wiki_syntax(self):
        return []

    def get_link_resolvers(self):
        def _format_link(formatter, ns, name, label):
            try:
                name = int(name)
            except ValueError:
                return label
            build = Build.fetch(self.env, name)
            if build:
                config = BuildConfig.fetch(self.env, build.config)
                title = 'Build %d ([%s] of %s) by %s' % (build.id, build.rev,
                        config.label, build.slave)
                return '<a class="build" href="%s" title="%s">%s</a>' \
                       % (formatter.href.build(build.config, build.id), title,
                          label)
            return label
        yield 'build', _format_link

    # IResourceManager methods
    
    def get_resource_realms(self):
        yield 'build'

    def get_resource_url(self, resource, href, **kwargs):
        config_name, build_id = self._parse_resource(resource.id)
        return href.build(config_name, build_id)

    def get_resource_description(self, resource, format=None, context=None,
                                 **kwargs):
        config_name, build_id = self._parse_resource(resource.id)
        config = BuildConfig.fetch(self.env, config_name)
        config_label = config and config.label and config.label or config_name
        if context:
            if build_id:
                return tag.a('Build %d ("%s")' % (build_id, config_label),
                        href=href.build(config_name, build_id))
            elif config_name:
                return tag.a('Build Configuration "%s"' % config_label,
                        href=href.build(config_name, build_id))
        else:
            if build_id:
                return 'Build %d ("%s")' % (build_id, config_label)
            elif config_name:
                return 'Build Configuration  "%s"' % config_label
        self.log.error("Unknown build/config resource.id: %s" % resource.id)
        return 'Unknown Build or Config'

    def _parse_resource(self, resource_id):
        """ Returns a (config_name, build_id) tuple. """
        r = resource_id.split('/', 1)
        if len(r) == 1:
            return r[0], None
        elif len(r) == 2:
            try:
                return r[0], int(r[1])
            except:
                return r[0], None
        return None, None

    # ILegacyAttachmentPolicyDelegate methods

    def check_attachment_permission(self, action, username, resource, perm):
        """ Respond to the various actions into the legacy attachment
        permissions used by the Attachment module. """
        if resource.parent.realm == 'build':
            if action == 'ATTACHMENT_VIEW':
                return 'BUILD_VIEW' in perm(resource.parent)
            elif action == 'ATTACHMENT_CREATE':
                return 'BUILD_MODIFY' in perm(resource.parent) \
                        or 'BUILD_CREATE' in perm(resource.parent)
            elif action == 'ATTACHMENT_DELETE':
                return 'BUILD_DELETE' in perm(resource.parent)
