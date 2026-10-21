"""Regression tests for recoverable CEO start and impossible empty deliveries."""
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
import hq_router as router
import hq_store as store
from tests.test_hq_projects import FakeAI, SPEC


@unittest.skipUnless(shutil.which('git'), 'git required')
class PlanRecoveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / 'hq.sqlite3'
        self.dest = self.root / 'products'
        ctx = mock.patch.object(core, 'STATE', self.root / 'state.json')
        ctx.start()
        self.addCleanup(ctx.stop)
        store.update_settings({'projects_root': str(self.dest)}, self.db)
        self.pid = hp.new_product('Recover', 'oyun', self.db)['id']
        hp._set(self.pid, self.db, spec=json.dumps(SPEC['spec'], ensure_ascii=False))

    def test_ai_exception_retries_same_folder(self):
        class Once(FakeAI):
            fail = True
            def __call__(self, role, prompt, cwd, dept, **kw):
                if role == 'breakdown' and self.fail:
                    self.fail = False
                    raise RuntimeError('AI geçici olarak yok')
                return super().__call__(role, prompt, cwd, dept, **kw)
        ai = Once(('PASS',) * 4)
        with self.assertRaises(RuntimeError):
            hp.start(self.pid, self.db, ai=ai)
        p = hp.get(self.pid, self.db)
        self.assertEqual((p['stage'], len(p['packages'])), ('planlama', 0))
        saved = Path(p['folder'])
        self.assertTrue((saved / '.studio' / hp.MARKER).exists())
        (saved / 'manual.txt').write_text('keep')
        again = hp.start(self.pid, self.db, ai=ai)
        self.assertEqual(again['stage'], 'uretim')
        self.assertEqual(Path(again['folder']), saved)
        self.assertTrue(again['packages'])
        self.assertEqual((saved / 'manual.txt').read_text(), 'keep')
        self.assertEqual(len(list(self.dest.iterdir())), 1)

    def test_failed_ai_response_keeps_planning(self):
        class Failed(FakeAI):
            def __call__(self, role, prompt, cwd, dept, **kw):
                if role == 'breakdown':
                    return dict(ok=False, output='CLI error', provider='Codex', model='test', effort='')
                return super().__call__(role, prompt, cwd, dept, **kw)
        with self.assertRaisesRegex(RuntimeError, 'iş planını oluşturamadı'):
            hp.start(self.pid, self.db, ai=Failed())
        self.assertEqual(hp.get(self.pid, self.db)['stage'], 'planlama')
        self.assertFalse(hp.get(self.pid, self.db)['packages'])

    def test_missing_cli_does_not_make_directory(self):
        with mock.patch.object(router, 'installed', return_value={}):
            with self.assertRaisesRegex(ValueError, 'CLI kur'):
                hp.start(self.pid, self.db)
        self.assertFalse(self.dest.exists())
        self.assertEqual(hp.get(self.pid, self.db)['folder'], '')

    def test_legacy_no_packages_can_retry(self):
        hp.start(self.pid, self.db, ai=FakeAI())
        old = hp.get(self.pid, self.db)['folder']
        with hp._Tx(self.db) as db:
            db.execute('DELETE FROM packages WHERE product_id=?', (self.pid,))
        p = hp.start(self.pid, self.db, ai=FakeAI())
        self.assertEqual((p['stage'], p['folder']), ('uretim', old))
        self.assertTrue(p['packages'])

    def test_retry_refuses_foreign_marker(self):
        hp.start(self.pid, self.db, ai=FakeAI())
        with hp._Tx(self.db) as db:
            db.execute('DELETE FROM packages WHERE product_id=?', (self.pid,))
        folder = Path(hp.get(self.pid, self.db)['folder'])
        marker = folder / '.studio' / hp.MARKER
        marker.write_text('P-foreign')
        with self.assertRaisesRegex(ValueError, 'doğrulanamadı'):
            hp.start(self.pid, self.db, ai=FakeAI())
        self.assertTrue(folder.exists())

    def test_no_packages_never_produces_delivery(self):
        ai = FakeAI()
        hp.start(self.pid, self.db, ai=ai)
        with hp._Tx(self.db) as db:
            db.execute('DELETE FROM packages WHERE product_id=?', (self.pid,))
        with self.assertRaisesRegex(ValueError, 'iş paketi yok'):
            hp.run_production(self.pid, self.db, ai=ai, tester=lambda _: (True, 'OK'))
        p = hp.get(self.pid, self.db)
        self.assertNotEqual(p['stage'], 'teslim')
        with self.assertRaisesRegex(ValueError, 'Tamamlanan iş paketi yok'):
            hp._deliver(self.pid, self.db, lambda _: (True, 'OK'), ai)

    def test_every_package_skipped_stops_not_delivers(self):
        ai = FakeAI()
        p = hp.start(self.pid, self.db, ai=ai)
        for item in p['packages']:
            hp._pkg(item['id'], self.db, status='atlandi')
        p = hp.run_production(self.pid, self.db, ai=ai, tester=lambda _: (True, 'OK'))
        self.assertEqual(p['stage'], 'durdu')
        self.assertFalse((Path(p['folder']) / '.studio' / 'TESLIM.md').exists())

    def test_plan_is_frozen_after_preparation(self):
        class Failed(FakeAI):
            def __call__(self, role, prompt, cwd, dept, **kw):
                if role == 'breakdown':
                    raise OSError('offline')
                return super().__call__(role, prompt, cwd, dept, **kw)
        with self.assertRaises(OSError):
            hp.start(self.pid, self.db, ai=Failed())
        with self.assertRaisesRegex(ValueError, 'tarif değiştirilemez'):
            hp.chat(self.pid, 'Motor değişsin', self.db, ai=FakeAI())


if __name__ == '__main__':
    unittest.main()
