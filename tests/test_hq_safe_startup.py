"""Safe 'Bunu yap' startup: preserve occupied folders, rollback only new reservations and verify engines."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
sys.path.insert(0, str(ROOT))
import core
import hq_projects as hp
import hq_store as store
from tests.test_hq_projects import FakeAI


@unittest.skipUnless(shutil.which('git'), 'git executable unavailable')
class SafeStartupTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.work = self.root / 'products'
        self.db = self.root / 'hq.sqlite3'
        patch = mock.patch.object(core, 'STATE', self.root / 'state.json')
        patch.start()
        self.addCleanup(patch.stop)
        store.update_settings({'projects_root': str(self.work)}, self.db)
        self.source = core.create_project(self.root, 'OriginalGodot', 'godot', 'original')
        self.original = self.source / 'scenes' / 'main.tscn'
        self.before = self.original.read_bytes()

    def plan(self, name='Vadi', engine='godot'):
        p = hp.new_product(name, 'oyun', self.db)
        hp._set(p['id'], self.db, spec=json.dumps({
            'name': name, 'engine': engine, 'summary': 'Oyun sahnesi',
            'features': ['Gemi hareketi'], 'acceptance': ['Gemi hareket eder']}))
        return hp.get(p['id'], self.db)

    def start(self, product, existing=''):
        return hp.start(product['id'], self.db, ai=FakeAI(), existing_folder=existing)

    def test_matching_marker_never_authorizes_deletion(self):
        p = self.plan()
        legacy = self.work / ('Vadi-kopya-' + p['id'][2:])
        (legacy / '.studio').mkdir(parents=True)
        (legacy / '.studio' / hp.MARKER).write_text(p['id'], encoding='utf-8')
        (legacy / 'my_changes.gd').write_text('work in progress', encoding='utf-8')
        made = self.start(p, str(self.source))
        self.assertNotEqual(Path(made['folder']), legacy)
        self.assertEqual((legacy / 'my_changes.gd').read_text(), 'work in progress')
        self.assertEqual(self.original.read_bytes(), self.before)

    def test_name_collision_never_deletes_foreign_folder(self):
        p = self.plan()
        # Deliberate path collision at the sanitized, full-ID product path.
        used = self.work / core.safe_name('Vadi-' + p['id'][2:])
        used.mkdir(parents=True)
        (used / 'personal.txt').write_text('keep')
        made = self.start(p)
        self.assertNotEqual(Path(made['folder']), used)
        self.assertEqual((used / 'personal.txt').read_text(), 'keep')
        self.assertTrue((Path(made['folder']) / 'project.godot').is_file())

    def test_existing_project_wrong_engine_rejected_without_writes(self):
        p = self.plan(engine='web')
        with self.assertRaisesRegex(ValueError, 'motoru'):
            self.start(p, str(self.source))
        self.assertFalse(self.work.exists() and any(self.work.iterdir()))
        self.assertEqual(self.original.read_bytes(), self.before)
        self.assertEqual(hp.get(p['id'], self.db)['stage'], 'planlama')

    def test_failure_inside_core_create_project_cleans_new_reservation(self):
        p = self.plan(engine='web')
        existing = self.work / 'DontDelete'
        existing.mkdir(parents=True)
        (existing / 'notes.txt').write_text('leave unchanged', encoding='utf-8')

        def fails_after_writing(root, name, engine, desc):
            target = Path(root) / name
            self.assertTrue(target.is_dir())  # reserved BEFORE core.create_project
            (target / 'partly_created.html').write_text('partial', encoding='utf-8')
            raise OSError(28, 'no space')

        with mock.patch.object(core, 'create_project', side_effect=fails_after_writing):
            with self.assertRaises(OSError):
                self.start(p)
        self.assertEqual(sorted(x.name for x in self.work.iterdir()), ['DontDelete'])
        self.assertEqual((existing / 'notes.txt').read_text(), 'leave unchanged')
        self.assertEqual(self.original.read_bytes(), self.before)
        self.assertEqual(hp.get(p['id'], self.db)['stage'], 'planlama')
        made = self.start(p)
        self.assertTrue((Path(made['folder']) / 'index.html').exists())

    def test_very_long_name_reservation_matches_core_target(self):
        p = self.plan(name='uzun-' + 'ab' * 90)
        made = self.start(p)
        folder = Path(made['folder'])
        self.assertLessEqual(len(folder.name), 50)
        self.assertEqual(folder.name, core.safe_name(folder.name))
        self.assertTrue((folder / 'project.godot').exists())
        self.assertTrue((folder / '.git').exists())
        self.assertEqual(set(self.work.iterdir()), {folder})

    def test_new_project_never_uses_empty_preexisting_directory(self):
        p = self.plan()
        existing = self.work / core.safe_name('Vadi-' + p['id'][2:])
        existing.mkdir(parents=True)  # empty, but belongs to somebody else
        made = self.start(p)
        self.assertNotEqual(Path(made['folder']), existing)
        self.assertTrue(existing.is_dir())
        self.assertEqual(list(existing.iterdir()), [])

if __name__ == '__main__':
    unittest.main()
