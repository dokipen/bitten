#-*- coding: utf-8 -*-
#
# Copyright (C) 2007 Ole Trenner, <ole@jayotee.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.

import unittest

from trac.db import DatabaseManager
from trac.test import EnvironmentStub, Mock
from trac.web.session import DetachedSession
from bitten.model import schema, Build, BuildStep, BuildLog
from bitten.notify import BittenNotify, BuildNotifyEmail


class BittenNotifyBaseTest(unittest.TestCase):
    def setUp(self):
        self.env = EnvironmentStub(enable=['trac.*', 'bitten.notify.*'])
        repos = Mock(get_changeset=lambda rev: Mock(author='author', rev=rev))
        self.env.get_repository = lambda authname=None: repos

        db = self.env.get_db_cnx()
        cursor = db.cursor()
        connector, _ = DatabaseManager(self.env)._get_connector()
        for table in schema:
            for stmt in connector.to_sql(table):
                cursor.execute(stmt)
        db.commit()


class BittenNotifyTest(BittenNotifyBaseTest):
    """unit tests for BittenNotify dispatcher class"""
    def setUp(self):
        BittenNotifyBaseTest.setUp(self)
        self.dispatcher = BittenNotify(self.env)
        self.failed_build = Build(self.env, status=Build.FAILURE)
        self.successful_build = Build(self.env, status=Build.SUCCESS)

    def test_do_notify_on_failed_build(self):
        self.set_option(BittenNotify.notify_on_failure, 'true')
        self.assertTrue(self.dispatcher._should_notify(self.failed_build),
                'notifier should be called for failed builds.')

    def test_do_not_notify_on_failed_build(self):
        self.set_option(BittenNotify.notify_on_failure, 'false')
        self.assertFalse(self.dispatcher._should_notify(self.failed_build),
                'notifier should not be called for failed build.')

    def test_do_notify_on_successful_build(self):
        self.set_option(BittenNotify.notify_on_success, 'true')
        self.assertTrue(self.dispatcher._should_notify(self.successful_build),
                'notifier should be called for successful builds when configured.')

    def test_do_not_notify_on_successful_build(self):
        self.set_option(BittenNotify.notify_on_success, 'false')
        self.assertFalse(self.dispatcher._should_notify(self.successful_build),
                'notifier should not be called for successful build.')

    def set_option(self, option, value):
        self.env.config.set(option.section, option.name, value)


class BuildNotifyEmailTest(BittenNotifyBaseTest):
    """unit tests for BittenNotifyEmail class"""
    def setUp(self):
        BittenNotifyBaseTest.setUp(self)
        self.env.config.set('notification','smtp_enabled','true')
        self.notifications_sent_to = []
        def send(to, cc, hdrs={}):
            self.notifications_sent_to = to
        def noop(*args, **kw):
            pass
        self.email = Mock(BuildNotifyEmail, self.env,
                          begin_send=noop,
                          finish_send=noop,
                          send=send)
        self.build = Build(self.env, status=Build.SUCCESS, rev=123)

    def test_notification_is_sent_to_author(self):
        self.email.notify(self.build)
        self.assertTrue('author' in self.notifications_sent_to,
                'Recipient list should contain the author')

    # TODO functional tests of generated mails


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(BittenNotifyTest, 'test'))
    suite.addTest(unittest.makeSuite(BuildNotifyEmailTest, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
