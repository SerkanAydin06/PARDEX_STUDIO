"""Offline review tests: no AI, Docker, network or subscriber usage."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import change_review as r


class ChangeReviewTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = Path(temp.name)
        self.project = self.home / 'game'
        self.project.mkdir()
        (self.project / 'project.godot').write_text('config_version=5')
        self.proposal = self.home / 'ai-draft'
        self.proposal.mkdir()
        (self.project / 'scripts').mkdir()
        (self.proposal / 'scripts').mkdir()
        self.original = self.project / 'scripts' / 'player.gd'
        self.candidate = self.proposal / 'scripts' / 'player.gd'
        self.original.write_text('extends Node\nvar hp = 3\n')
        self.candidate.write_text('extends Node\nvar hp = 4\n')
        self.store = self.home / 'private_review_store'

    def stage(self, *paths):
        return r.stage(self.project, self.proposal, list(paths or ('scripts/player.gd',)),home=self.store)

    def test_staging_does_not_edit_project(self):
        item = self.stage()
        self.assertEqual('staged', item['state'])
        self.assertIn('hp = 3', self.original.read_text())
        self.assertEqual(len(item['digest']), 64)
        self.assertIn('hp = 4', r.diff(item['review_id'], home=self.store))

    def test_owner_approval_and_exact_digest_are_required(self):
        item = self.stage()
        with self.assertRaises(PermissionError):
            r.apply(item['review_id'], item['digest'], home=self.store)
        with self.assertRaises(PermissionError):
            r.apply(item['review_id'], '0'*64, owner_confirms=True, home=self.store)
        self.assertIn('hp = 3', self.original.read_text())
        result = r.apply(item['review_id'], item['digest'], owner_confirms=True,home=self.store)
        self.assertEqual('applied', result['state'])
        self.assertIn('hp = 4', self.original.read_text())
        with self.assertRaises(RuntimeError):
            r.apply(item['review_id'], item['digest'],owner_confirms=True,home=self.store)

    def test_stale_source_blocks_apply(self):
        item=self.stage()
        self.original.write_text('extends Node\nvar hp = 900\n')
        with self.assertRaisesRegex(ValueError, 'changed'):
            r.apply(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.assertIn('900',self.original.read_text())
        self.assertEqual('staged',r.summary(item['review_id'],home=self.store)['state'])

    def test_staged_snapshot_tampering_blocks_apply(self):
        item=self.stage()
        snap=self.store/item['review_id']/'after'/'scripts'/'player.gd'
        snap.write_text('malicious change')
        with self.assertRaisesRegex(ValueError,'snapshot|proposal'):
            r.apply(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.assertIn('hp = 3',self.original.read_text())

    def test_duplicate_and_path_traversal_blocked(self):
        for path in ('../secret.py','/absolute.py', '.studio/data.json',
                     'scripts/../../outside.py','scripts/.env','AGENTS.md',
                     'scripts/CON.py','scripts/foo.exe','scripts//player.gd'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.stage(path)
        with self.assertRaises(ValueError):
            self.stage('scripts/player.gd','scripts/player.gd')

    def test_symlink_source_and_destination_are_rejected(self):
        symlink=self.proposal/'scripts'/'external.py'
        try:
            symlink.symlink_to(self.candidate)
        except OSError:
            self.skipTest('Symlinks unavailable')
        with self.assertRaises(ValueError):
            self.stage('scripts/external.py')
        self.candidate.unlink()
        self.candidate.symlink_to(self.original)
        with self.assertRaises(ValueError):
            self.stage()

    def test_private_store_cannot_be_inside_project(self):
        with self.assertRaises(ValueError):
            r.stage(self.project,self.proposal,['scripts/player.gd'],home=self.project/'reviews')

    def test_large_files_and_binary_blocked(self):
        self.candidate.write_bytes(b'x'*(r.MAX_FILE_BYTES+1))
        with self.assertRaises(ValueError):self.stage()
        self.candidate.write_bytes(b'\x00hello')
        with self.assertRaises(ValueError):self.stage()

    def test_new_file_apply_then_rollback(self):
        new=self.proposal/'scripts'/'new.gd'
        new.write_text('extends Node')
        item=self.stage('scripts/new.gd')
        self.assertFalse((self.project/'scripts'/'new.gd').exists())
        r.apply(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.assertTrue((self.project/'scripts'/'new.gd').exists())
        r.rollback(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.assertFalse((self.project/'scripts'/'new.gd').exists())

    def test_modified_file_rollback_and_no_double_rollback(self):
        item=self.stage()
        r.apply(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        with self.assertRaises(PermissionError):
            r.rollback(item['review_id'],item['digest'],home=self.store)
        r.rollback(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.assertIn('hp = 3',self.original.read_text())
        with self.assertRaises(RuntimeError):
            r.rollback(item['review_id'],item['digest'],owner_confirms=True,home=self.store)

    def test_rollback_refuses_destroying_new_user_edit(self):
        item=self.stage()
        r.apply(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.original.write_text('human work')
        with self.assertRaises(RuntimeError):
            r.rollback(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.assertEqual('human work',self.original.read_text())

    def test_partial_apply_error_rolls_back_all(self):
        (self.original.parent/'health.gd').write_text('health = 1')
        (self.proposal/'scripts'/'health.gd').write_text('health = 2')
        item=self.stage('scripts/player.gd','scripts/health.gd')
        original_write=r._write_atomic
        calls=[]
        def fail_once(path,data):
            calls.append(str(path))
            if len(calls)==2:
                raise OSError('disk error')
            return original_write(path,data)
        with mock.patch.object(r,'_write_atomic',side_effect=fail_once):
            with self.assertRaises(OSError):
                r.apply(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.assertIn('hp = 3',self.original.read_text())
        self.assertEqual('health = 1',(self.original.parent/'health.gd').read_text())
        self.assertEqual('rolled_back',r.summary(item['review_id'],home=self.store)['state'])

    def test_locked_review_fails_closed(self):
        item=self.stage()
        lock=self.store/item['review_id']/'busy.lock'
        lock.write_text('locked')
        with self.assertRaises(FileExistsError):
            r.apply(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.assertIn('hp = 3',self.original.read_text())

    def test_diff_does_not_expose_raw_common_token(self):
        item=self.stage()
        d=r.diff(item['review_id'],home=self.store)
        self.assertIn('player.gd',d)
        self.assertTrue(len(d)<=9000)



    def test_case_insensitive_private_path_rejected(self):
        for path in ('SeCrEtS/token.py','scripts/agents.md','scripts/CLAUDE.md'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.stage(path)

    def test_store_cannot_be_inside_ai_proposal(self):
        with self.assertRaises(ValueError):
            r.stage(self.project,self.proposal,['scripts/player.gd'],home=self.proposal/'review_store')

    def test_rollback_prechecks_all_before_any_mutation(self):
        (self.original.parent/'health.gd').write_text('health = 1')
        (self.proposal/'scripts'/'health.gd').write_text('health = 2')
        item = self.stage('scripts/player.gd', 'scripts/health.gd')
        r.apply(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.original.write_text('human manual update')
        with self.assertRaises(RuntimeError):
            r.rollback(item['review_id'],item['digest'],owner_confirms=True,home=self.store)
        self.assertEqual('health = 2',(self.original.parent/'health.gd').read_text())
        self.assertEqual('human manual update',self.original.read_text())


if __name__=='__main__': unittest.main()
