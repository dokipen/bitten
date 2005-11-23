# -*- coding: iso8859-1 -*-
#
# Copyright (C) 2005 Christopher Lenz <cmlenz@gmx.de>
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution. The terms
# are also available at http://bitten.cmlenz.net/wiki/License.

import md5
import os
import shutil
import tarfile
import tempfile
import unittest

from trac.test import EnvironmentStub, Mock
from bitten.model import BuildConfig
from bitten.snapshot import SnapshotManager
from bitten.util import md5sum


class SnapshotManagerTestCase(unittest.TestCase):

    def setUp(self):
        self.env = EnvironmentStub()
        self.env.path = tempfile.mkdtemp(prefix='bitten_test')
        os.mkdir(os.path.join(self.env.path, 'snapshots'))
        db = self.env.get_db_cnx()
        cursor = db.cursor()
        for table in BuildConfig._schema:
            for stmt in db.to_sql(table):
                cursor.execute(stmt)
        db.commit()
        self.config = BuildConfig(self.env, name='foo', path='trunk')
        self.config.insert()

    def tearDown(self):
        shutil.rmtree(self.env.path)

    def _create_file(self, path, create_md5sum=True):
        filename = os.path.join(self.env.path, path)
        fileobj = file(filename, 'w')
        fileobj.close()
        if create_md5sum:
            md5sum.write(filename)
        return filename

    def test_empty(self):
        snapshots = SnapshotManager(self.config)
        self.assertEqual([], snapshots._index)
        self.assertEqual(None, snapshots.get(123))

    def test_get(self):
        path1 = self._create_file(os.path.join('snapshots', 'foo_r123.tar.bz2'))
        path2 = self._create_file(os.path.join('snapshots', 'foo_r124.tar.bz2'))
        snapshots = SnapshotManager(self.config)
        self.assertEqual(path1, snapshots.get(123))
        self.assertEqual(path2, snapshots.get(124))

    def test_get_prefix_match(self):
        path1 = self._create_file(os.path.join('snapshots', 'foo_r123.tar.bz2'))
        self._create_file(os.path.join('snapshots', 'bar_r124.tar.bz2'))
        snapshots = SnapshotManager(self.config)
        self.assertEqual(path1, snapshots.get(123))
        self.assertEqual(None, snapshots.get(124))

    def test_get_wrong_extension(self):
        path1 = self._create_file(os.path.join('snapshots', 'foo_r123.tar.bz2'))
        self._create_file(os.path.join('snapshots', 'foo_r124.doc'))
        snapshots = SnapshotManager(self.config)
        self.assertEqual(path1, snapshots.get(123))
        self.assertEqual(None, snapshots.get(124))

    def test_get_missing_rev(self):
        path1 = self._create_file(os.path.join('snapshots', 'foo_r123.tar.bz2'))
        self._create_file(os.path.join('snapshots', 'foo124.doc'))
        snapshots = SnapshotManager(self.config)
        self.assertEqual(path1, snapshots.get(123))
        self.assertEqual(None, snapshots.get(124))

    def test_get_missing_md5sum(self):
        path1 = self._create_file(os.path.join('snapshots', 'foo_r123.tar.bz2'))
        self._create_file(os.path.join('snapshots', 'foo_r124.zip'),
                          create_md5sum=False)
        snapshots = SnapshotManager(self.config)
        self.assertEqual(path1, snapshots.get(123))
        self.assertEqual(None, snapshots.get(124))

    def test_get_wrong_md5sum(self):
        path1 = self._create_file(os.path.join('snapshots', 'foo_r123.tar.bz2'))
        path2 = self._create_file(os.path.join('snapshots', 'foo_r124.tar.bz2'),
                                 create_md5sum=False)
        
        md5sum.write(path1, path2 + '.md5')
        snapshots = SnapshotManager(self.config)
        self.assertEqual(path1, snapshots.get(123))
        self.assertEqual(None, snapshots.get(124))

    def test_cleanup_on_init(self):
        self.env.config.set('bitten', 'max_snapshots', '3')
        path1 = self._create_file(os.path.join('snapshots', 'foo_r123.tar.bz2'))
        path2 = self._create_file(os.path.join('snapshots', 'foo_r124.tar.bz2'))
        path3 = self._create_file(os.path.join('snapshots', 'foo_r125.tar.bz2'))
        self._create_file(os.path.join('snapshots', 'foo_r126.tar.bz2'))
        snapshots = SnapshotManager(self.config)
        self.assertEqual(path1, snapshots.get(123))
        self.assertEqual(path2, snapshots.get(124))
        self.assertEqual(path3, snapshots.get(125))
        self.assertEqual(None, snapshots.get(126))

    def test_cleanup_explicit(self):
        path1 = self._create_file(os.path.join('snapshots', 'foo_r123.tar.bz2'))
        path2 = self._create_file(os.path.join('snapshots', 'foo_r124.tar.bz2'))
        path3 = self._create_file(os.path.join('snapshots', 'foo_r125.tar.bz2'))
        snapshots = SnapshotManager(self.config)
        path4 = self._create_file(os.path.join('snapshots', 'foo_r126.tar.bz2'))
        snapshots._index.append((os.path.getmtime(path4), 126, path4))
        snapshots._cleanup(3)
        self.assertEqual(path1, snapshots.get(123))
        self.assertEqual(path2, snapshots.get(124))
        self.assertEqual(path3, snapshots.get(125))
        self.assertEqual(None, snapshots.get(126))

    def test_create_not_a_directory(self):
        repos = Mock(get_node=lambda path, rev: Mock(isdir=False))
        self.env.get_repository = lambda authname=None: repos
        snapshots = SnapshotManager(self.config)
        self.assertRaises(AssertionError, snapshots.create, 123)

    def test_create_empty(self):
        root_dir = Mock(isdir=True, get_entries=lambda: [], path='trunk',
                        rev=123)
        repos = Mock(get_node=lambda path, rev: root_dir)
        self.env.get_repository = lambda authname=None: repos
        snapshots = SnapshotManager(self.config)
        snapshots.create(123).join()
        path = snapshots.get(123)
        assert path is not None
        assert path.endswith('foo_r123.tar.bz2')
        entries = tarfile.open(path, 'r:bz2').getmembers()
        self.assertEqual(1, len(entries))
        self.assertEqual('foo_r123/', entries[0].name)

    def test_create_empty_dir(self):
        empty_dir = Mock(isdir=True, get_entries=lambda: [], path='trunk/empty')
        root_dir = Mock(isdir=True, get_entries=lambda: [empty_dir],
                        path='trunk', rev=123)
        repos = Mock(get_node=lambda path, rev: root_dir)
        self.env.get_repository = lambda authname=None: repos
        snapshots = SnapshotManager(self.config)
        snapshots.create(123).join()
        path = snapshots.get(123)
        assert path is not None
        assert path.endswith('foo_r123.tar.bz2')
        entries = tarfile.open(path, 'r:bz2').getmembers()
        self.assertEqual(2, len(entries))
        self.assertEqual('foo_r123/', entries[0].name)
        self.assertEqual('foo_r123/empty/', entries[1].name)

    def test_get_closest_match_backward(self):
        path1 = self._create_file(os.path.join('snapshots', 'foo_r123.tar.bz2'))
        path2 = self._create_file(os.path.join('snapshots', 'foo_r124.tar.bz2'))

        empty_dir = Mock(isdir=True, get_entries=lambda: [], path='trunk/empty')
        root_dir = Mock(isdir=True, get_entries=lambda: [empty_dir],
                        path='trunk', rev=125)
        repos = Mock(get_node=lambda path, rev: root_dir,
                     normalize_rev=lambda rev: int(rev),
                     rev_older_than=lambda rev1, rev2: rev1 < rev2,
                     next_rev=lambda rev: int(rev) + 1,
                     previous_rev=lambda rev: int(rev) - 1)
        self.env.get_repository = lambda authname=None: repos

        snapshots = SnapshotManager(self.config)
        match = snapshots._get_closest_match(repos, root_dir)
        self.assertEqual((124, path2), match)

    def test_get_closest_match_forward(self):
        path1 = self._create_file(os.path.join('snapshots', 'foo_r123.tar.bz2'))
        path2 = self._create_file(os.path.join('snapshots', 'foo_r124.tar.bz2'))

        empty_dir = Mock(isdir=True, get_entries=lambda: [], path='trunk/empty')
        root_dir = Mock(isdir=True, get_entries=lambda: [empty_dir],
                        path='trunk', rev=122)
        repos = Mock(get_node=lambda path, rev: root_dir,
                     normalize_rev=lambda rev: int(rev),
                     rev_older_than=lambda rev1, rev2: rev1 < rev2,
                     next_rev=lambda rev: int(rev) + 1,
                     previous_rev=lambda rev: int(rev) - 1)
        self.env.get_repository = lambda authname=None: repos

        snapshots = SnapshotManager(self.config)
        match = snapshots._get_closest_match(repos, root_dir)
        self.assertEqual((123, path1), match)


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(SnapshotManagerTestCase, 'test'))
    return suite

if __name__ == '__main__':
    unittest.main(defaultTest='suite')
