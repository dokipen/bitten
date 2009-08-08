# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2007 Christopher Lenz <cmlenz@gmx.de>
# Copyright (C) 2007 Edgewall Software
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.edgewall.org/wiki/License.

import unittest


def master_suite():
    from bitten.tests import admin, master, model, queue, web_ui, notify
    from bitten.report import tests as report
    suite = unittest.TestSuite()
    suite.addTest(admin.suite())
    suite.addTest(master.suite())
    suite.addTest(model.suite())
    suite.addTest(queue.suite())
    suite.addTest(web_ui.suite())
    suite.addTest(report.suite())
    suite.addTest(notify.suite())
    return suite

def suite():
    suite = unittest.TestSuite()
    try:
        import trac
        suite.addTest(master_suite())
    except ImportError:
        print "\nTrac not installed -- Skipping master tests\n"
    import bitten.slave_tests
    suite.addTest(bitten.slave_tests.suite())
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
