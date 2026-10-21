"""A stopped ('durdu') project must always have a way forward, and 'Bunu yap' checks independent-review
capacity before copying anything or spending a call. Offline, fake AI."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
sys.path.insert(0, str(ROOT))
import core  # noqa: E402
import hq_projects as hp  # noqa: E402
import hq_router as router  # noqa: E402
import hq_store as store  # noqa: E402
from tests.test_hq_projects import FakeAI  # noqa: E402

NO_ENGINE = (False, 'Godot kurulu/bulunur degil. Test yapilmadi.')
OK = lambda f: (True, 'OK')  # noqa: E731


class ResumeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / 'hq.sqlite3'
        self.work = self.root / 'urunler'
        for p in (mock.patch.object(core, 'STATE', self.root / 'state.json'),
                  mock.patch.object(hp, '_scratch', lambda: str(self.root))):
            p.start()
            self.addCleanup(p.stop)
        store.update_settings({'projects_root': str(self.work)}, self.db)

    def product(self, name='Oyun'):
        p = hp.new_product(name, 'oyun', self.db)
        hp._set(p['id'], self.db, spec=json.dumps({'name': name, 'engine': 'web', 'summary': 'x',
                                                   'features': ['a', 'b'], 'acceptance': ['ok']}))
        return p['id']

    def test_paused_for_engine_install_can_resume(self):
        pid = self.product()
        hp.start(pid, self.db, ai=FakeAI())
        hp.run_production(pid, self.db, ai=FakeAI(), tester=lambda f: NO_ENGINE)
        q = hp.open_questions(self.db)[0]
        self.assertEqual(q['kind'], 'untested')
        hp.answer(q['id'], 'Durdur, motoru kurup sonra devam edeceğim', self.db)
        self.assertEqual(hp.get(pid, self.db)['stage'], 'durdu')
        # still no engine: asked again, nothing spent
        ai = FakeAI(('PASS',) * 6)
        p = hp.run_production(pid, self.db, ai=ai, tester=lambda f: NO_ENGINE)
        self.assertEqual(p['stage'], 'soru')
        self.assertEqual(ai.calls, [])
        hp.answer(hp.open_questions(self.db)[0]['id'], 'Durdur, motoru kurup sonra devam edeceğim', self.db)
        # engine installed: continues to delivery
        p = hp.run_production(pid, self.db, ai=ai, tester=OK)
        self.assertEqual(p['stage'], 'teslim')

    def test_all_skipped_project_accepts_change_request(self):
        pid = self.product()
        ai = FakeAI(('FAIL',) * 30)
        hp.start(pid, self.db, ai=ai)
        for _ in range(6):
            hp.run_production(pid, self.db, ai=ai, tester=OK)
            qs = hp.open_questions(self.db)
            if not qs:
                break
            hp.answer(qs[0]['id'], 'Bu paketi atla', self.db)
        p = hp.get(pid, self.db)
        self.assertEqual(p['stage'], 'durdu')
        self.assertIn('Değişiklik iste', p['chat'][-1]['text'])
        p = hp.run_production(pid, self.db, ai=ai, tester=OK)  # resuming is harmless, never an error
        self.assertEqual(p['stage'], 'durdu')
        p = hp.request_changes(pid, 'Daha basit bir iskeletle yeniden dene', self.db)
        self.assertEqual(p['stage'], 'uretim')
        p = hp.run_production(pid, self.db, ai=FakeAI(('PASS',) * 6), tester=OK)
        self.assertEqual(p['stage'], 'teslim')
        self.assertEqual([k['status'] for k in p['packages']].count('tamam'), 1)

    def test_change_request_needs_started_project(self):
        pid = self.product()
        with self.assertRaises(ValueError):
            hp.request_changes(pid, 'Bir şey değiştir lütfen', self.db)

    def test_start_checks_review_capacity_before_any_copy_or_call(self):
        pid = self.product()
        spent = []
        with mock.patch.object(router, 'installed', return_value={'Claude': 'claude'}), \
                mock.patch.object(router, 'call', side_effect=lambda *a, **k: spent.append(a)):
            with self.assertRaisesRegex(ValueError, 'en az 2 farklı AI'):
                hp.start(pid, self.db)
        self.assertEqual(spent, [])
        self.assertFalse(self.work.exists() and any(self.work.iterdir()))
        p = hp.get(pid, self.db)
        self.assertEqual((p['stage'], p['folder']), ('planlama', ''))


if __name__ == '__main__':
    unittest.main()
