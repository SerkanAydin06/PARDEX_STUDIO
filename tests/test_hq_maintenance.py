import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import hq_maintenance as maintenance


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / 'project.godot').write_text('[application]\n')

    def test_empty_reported_directory_is_backed_up_and_attempt_is_bounded(self):
        (self.root / 'export_templates').mkdir()
        output = "ERROR: Cannot go into subdir 'export_templates'."
        changed, report = maintenance.repair(self.root, output)
        self.assertTrue(changed)
        self.assertFalse((self.root / 'export_templates').exists())
        backups = list((self.root / '.studio/maintenance').glob('backup-*/export_templates'))
        self.assertEqual(len(backups), 1)
        self.assertTrue(backups[0].is_dir())
        self.assertIn('yedeklendi', report)
        self.assertFalse(maintenance.repair(self.root, output)[0])
        maintenance.resolved(self.root)
        self.assertFalse((self.root / '.studio/maintenance/attempted').exists())

    def test_only_editor_cache_moves_import_cache_and_sources_survive(self):
        editor = self.root / '.godot/editor'
        editor.mkdir(parents=True)
        (editor / 'project_metadata.cfg').write_text('old metadata')
        (self.root / '.godot/uid_cache.bin').write_bytes(b'uid')
        (self.root / 'Board.gd').write_text('extends Node')
        self.assertTrue(maintenance.repair(self.root, 'Safe save failed')[0])
        self.assertEqual((self.root / '.godot/uid_cache.bin').read_bytes(), b'uid')
        self.assertEqual((self.root / 'Board.gd').read_text(), 'extends Node')
        backup = next((self.root / '.studio/maintenance').glob('backup-*/godot-editor/project_metadata.cfg'))
        self.assertEqual(backup.read_text(), 'old metadata')

    def test_nonempty_referenced_and_unreported_dirs_are_preserved(self):
        for name in maintenance.EDITOR_DIRS:
            (self.root / name).mkdir()
        (self.root / 'export_templates/keep.txt').write_text('source')
        (self.root / 'main.gd').write_text('var path = "res://feature_profiles"')
        output = "Cannot go into subdir 'export_templates'\nCannot go into subdir 'feature_profiles'"
        self.assertFalse(maintenance.repair(self.root, output)[0])
        for name in maintenance.EDITOR_DIRS:
            self.assertTrue((self.root / name).is_dir())

    def test_denied_probe_does_not_mutate_cache(self):
        editor = self.root / '.godot/editor'
        editor.mkdir(parents=True)
        with mock.patch.object(maintenance, 'probe', side_effect=PermissionError('blocked')):
            changed, report = maintenance.repair(self.root, 'Safe save failed')
        self.assertFalse(changed)
        self.assertIn('blocked', report)
        self.assertTrue(editor.exists())
        self.assertFalse((self.root / '.studio').exists())

    def test_symlinked_state_is_never_written(self):
        outside = self.root / 'outside'
        outside.mkdir()
        try:
            (self.root / '.studio').symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest('symlinks unavailable')
        self.assertFalse(maintenance.repair(self.root, 'Safe save failed')[0])
        self.assertEqual(list(outside.iterdir()), [])

    def test_reparse_point_detection(self):
        fake = mock.Mock(st_mode=stat_mode(), st_file_attributes=0x400)
        with mock.patch.object(Path, 'lstat', return_value=fake):
            self.assertTrue(maintenance.linked(self.root))


def stat_mode():
    import stat
    return stat.S_IFDIR | 0o755


class CoreFaultTests(unittest.TestCase):
    def test_internal_fault_is_queued_once_without_exception_secrets(self):
        import core
        import hq_board as board
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'test.sqlite3'
            try:
                exec(compile('raise TypeError("private-token-value")', str(core.BASE / 'app/core.py'), 'exec'))
            except TypeError as exc:
                first = maintenance.report_core_fault(exc, db)
                second = maintenance.report_core_fault(exc, db)
            self.assertEqual(first, second)
            request = board.get_proposal(first, db)
            self.assertIn('TypeError', request['code_request'])
            self.assertNotIn('private-token-value', str(request))

    def test_os_error_does_not_become_a_core_patch(self):
        self.assertIsNone(maintenance.report_core_fault(PermissionError('denied')))
