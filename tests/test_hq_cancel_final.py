"""Cancelling a project is final: no answer, finished planning, or new question can revive it, and the
planning AI call itself is stopped. Offline, fake AI."""
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

NO_ENGINE = lambda f: (False, 'Godot kurulu/bulunur degil. Test yapilmadi.')  # noqa: E731
OK = lambda f: (True, 'OK')  # noqa: E731


class CancelFinalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / 'hq.sqlite3'
        for p in (mock.patch.object(core, 'STATE', self.root / 'state.json'),
                  mock.patch.object(hp, '_scratch', lambda: str(self.root))):
            p.start()
            self.addCleanup(p.stop)
        store.update_settings({'projects_root': str(self.root / 'urunler')}, self.db)

    def product(self, name='Oyun'):
        p = hp.new_product(name, 'oyun', self.db)
        hp._set(p['id'], self.db, spec=json.dumps({'name': name, 'engine': 'web', 'summary': 'x',
                                                   'features': ['a', 'b'], 'acceptance': ['ok']}))
        return p['id']

    def test_cancel_during_ceo_planning_is_not_overridden(self):
        pid = self.product()
        base = FakeAI()

        def ai(role, prompt, cwd, dept, **kw):
            if role in ('breakdown', 'architect'):
                hp.cancel(pid, self.db)  # owner presses "Projeyi iptal et" while the CEO plans
            return base(role, prompt, cwd, dept, **kw)
        p = hp.start(pid, self.db, ai=ai)
        self.assertEqual(p['stage'], 'iptal')
        spend = FakeAI(('PASS',) * 6)
        p = hp.run_production(pid, self.db, ai=spend, tester=OK)  # what the server does next
        self.assertEqual(p['stage'], 'iptal')
        self.assertEqual(spend.calls, [])

    def test_cancel_stops_the_running_planning_call(self):
        pid = self.product()
        seen = {}

        def fake_call(role, prompt, cwd, dept, cancel_check=None, **kw):
            if role in ('breakdown', 'architect'):
                hp.cancel(pid, self.db)
                seen['stopped'] = cancel_check is not None and cancel_check()
                return {'ok': False, 'output': 'PARDEX: patron iptal/acil durdurma', 'provider': 'Codex',
                        'model': '', 'effort': '', 'reason': ''}
            return FakeAI()(role, prompt, cwd, dept, **kw)
        with mock.patch.object(router, 'installed', return_value={'Claude': 'c', 'Codex': 'x'}), \
                mock.patch.object(router, 'call', side_effect=fake_call):
            p = hp.start(pid, self.db)  # real (native) path: no error, quietly cancelled
        self.assertTrue(seen['stopped'])
        self.assertEqual(p['stage'], 'iptal')

    def test_cancelled_question_disappears_and_cannot_revive(self):
        pid = self.product()
        hp.start(pid, self.db, ai=FakeAI())
        hp.run_production(pid, self.db, ai=FakeAI(), tester=NO_ENGINE)
        q = hp.open_questions(self.db)[0]
        hp.cancel(pid, self.db)
        self.assertEqual(hp.open_questions(self.db), [])
        with self.assertRaises((KeyError, ValueError)):
            hp.answer(q['id'], q['options'][0], self.db)
        self.assertEqual(hp.get(pid, self.db)['stage'], 'iptal')

    def test_no_code_path_moves_a_cancelled_project(self):
        pid = self.product()
        hp.start(pid, self.db, ai=FakeAI())
        hp.cancel(pid, self.db)
        hp._set(pid, self.db, stage='uretim')
        self.assertIsNone(hp.ask(pid, 'ai', 'soru?', [], path=self.db))
        self.assertEqual(hp.get(pid, self.db)['stage'], 'iptal')
        with self.assertRaises(ValueError):
            hp.request_changes(pid, 'Yeniden başlat lütfen', self.db)
        with self.assertRaises(ValueError):
            hp.start(pid, self.db, ai=FakeAI())


if __name__ == '__main__':
    unittest.main()
