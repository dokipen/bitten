# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2006 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

"""Various methods for backwards compatibility with older Trac versions."""

def schema_to_sql(env, db, table):
    try:
        # Trac >= 0.10
        from trac.db import DatabaseManager
        connector, _ = DatabaseManager(env)._get_connector()
        return connector.to_sql(table)
    except ImportError:
        # Trac 0.9.x
        return db.to_sql(table)
