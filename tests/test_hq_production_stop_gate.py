"""Production cancellation and strict final acceptance gate: offline regression tests."""
import json
import shutil
import sys
import tempfile
import time
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


@unittest.skipUnless(shutil.which('git'), 'git required for HQ projects')
class ProductionSafetyTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / 'hq.sqlite3'
        state_patch = mock.patch.object(core, 'STATE', self.root / 'state.json')
        state_patch.start()
        self.addCleanup(state_patch.stop)
        store.update_settings({'projects_root': str(self.root / 'products')}, self.db)
        item = hp.new_product('Safety', 'oyun', self.db)
        self.pid = item['id']
        hp._set(self.pid, self.db, spec=json.dumps(SPEC['spec'], ensure_ascii=False))
        hp.start(self.pid, self.db, ai=FakeAI())

    def folder(self):
        return Path(hp.get(self.pid, self.db)['folder'])

    def test_owner_cancel_during_ai_prevents_review_and_delivery(self):
        outer = self
        class CancelOnImplement(FakeAI):
            def __call__(self, role, prompt, cwd, dept, **kwargs):
                response = super().__call__(role, prompt, cwd, dept, **kwargs)
                if role == 'implement':
                    hp.cancel(outer.pid, outer.db)
                return response
        ai = CancelOnImplement(('PASS',) * 7)
        p = hp.run_production(self.pid, self.db, ai=ai, tester=lambda _: (True, 'OK'))
        self.assertEqual(p['stage'], 'iptal')
        self.assertEqual([c[0] for c in ai.calls], ['implement'])
        self.assertFalse((self.folder() / '.studio' / 'TESLIM.md').exists())
        self.assertFalse(any(x['status'] == 'tamam' for x in p['packages']))

    def test_emergency_pause_during_ai_stops_then_can_resume(self):
        outer = self
        class PauseOnImplement(FakeAI):
            pause_once = True
            def __call__(self, role, prompt, cwd, dept, **kwargs):
                response = super().__call__(role, prompt, cwd, dept, **kwargs)
                if role == 'implement' and self.pause_once:
                    self.pause_once = False
                    store.update_settings({'paused': True}, outer.db)
                return response
        ai = PauseOnImplement(('PASS',) * 8)
        p = hp.run_production(self.pid, self.db, ai=ai, tester=lambda _: (True, 'OK'))
        self.assertEqual(p['stage'], 'durdu')
        self.assertEqual([c[0] for c in ai.calls], ['implement'])
        self.assertFalse((self.folder() / '.studio' / 'TESLIM.md').exists())
        store.update_settings({'paused': False}, self.db)
        hp._set(self.pid, self.db, approved_calls=hp.get(self.pid, self.db)['approved_calls'] + 8)
        p = hp.run_production(self.pid, self.db, ai=ai, tester=lambda _: (True, 'OK'))
        self.assertEqual(p['stage'], 'teslim')

    def test_cancel_before_background_run_has_no_ai_calls(self):
        hp.cancel(self.pid, self.db)
        ai = FakeAI()
        p = hp.run_production(self.pid, self.db, ai=ai, tester=lambda _: (True, 'OK'))
        self.assertEqual(p['stage'], 'iptal')
        self.assertFalse(ai.calls)

    def test_pause_before_background_run_uses_no_ai_calls(self):
        store.update_settings({'paused': True}, self.db)
        ai = FakeAI()
        p = hp.run_production(self.pid, self.db, ai=ai, tester=lambda _: (True, 'OK'))
        self.assertEqual(p['stage'], 'durdu')
        self.assertFalse(ai.calls)

    def test_failing_final_engine_test_blocks_delivery(self):
        n = [0]
        def tests(_folder):
            n[0] += 1
            if n[0] >= 4:
                return False, 'Godot runtime crash in scene'
            return True, 'OK'
        p = hp.run_production(self.pid, self.db, ai=FakeAI(('PASS',) * 8), tester=tests)
        self.assertEqual(n[0], 4)
        self.assertEqual(p['stage'], 'durdu')
        self.assertTrue(all(x['status'] == 'tamam' for x in p['packages']))
        self.assertIn('Son kalite testi BAŞARISIZ', p['chat'][-1]['text'])
        self.assertFalse((self.folder() / '.studio' / 'TESLIM.md').exists())
        with self.assertRaisesRegex(ValueError, 'Teslim bekleyen'):
            hp.accept(self.pid, self.db)

    def test_testsiz_permission_does_not_waive_real_failure(self):
        hp._set(self.pid, self.db, allow_untested=1)
        checks = [0]
        def tester(_):
            checks[0] += 1
            return (False, 'AssertionError: movement broken') if checks[0] >= 3 else (True, 'OK')
        p = hp.run_production(self.pid, self.db, ai=FakeAI(('PASS',) * 8), tester=tester)
        self.assertEqual(p['stage'], 'durdu')
        self.assertFalse((self.folder() / '.studio' / 'TESLIM.md').exists())

    def test_explicit_testsiz_permission_still_allows_unavailable_engine(self):
        hp._set(self.pid, self.db, allow_untested=1)
        p = hp.run_production(self.pid, self.db, ai=FakeAI(('PASS',) * 8),
                              tester=lambda _: (False, 'Godot kurulu değil. Test YAPILMADI.'))
        self.assertEqual(p['stage'], 'teslim')
        self.assertIn('GEÇMEDİ / YAPILAMADI', p['report'])

    def test_owner_cancel_during_final_test_cannot_be_overwritten(self):
        runs = [0]
        def tester(_):
            runs[0] += 1
            if runs[0] == 4:
                hp.cancel(self.pid, self.db)
            return True, 'OK'
        p = hp.run_production(self.pid, self.db, ai=FakeAI(('PASS',) * 8), tester=tester)
        self.assertEqual(p['stage'], 'iptal')
        self.assertFalse((self.folder() / '.studio' / 'TESLIM.md').exists())

    def test_cancel_aware_native_subprocess_is_terminated(self):
        checks = [0]
        def stop():
            checks[0] += 1
            return checks[0] >= 3
        started = time.monotonic()
        result = core.run([sys.executable, '-c', 'import time;time.sleep(20)'], self.root,
                          timeout=20, cancel_check=stop)
        self.assertEqual(result.returncode, 130)
        self.assertIn('durdurma', result.stdout)
        self.assertLess(time.monotonic() - started, 6)

    def test_idle_completed_process_does_not_trigger_spurious_stop(self):
        result = core.run([sys.executable, '-c', 'print("SAFE")'], self.root,
                          timeout=3, cancel_check=lambda: False)
        self.assertEqual(result.returncode, 0)
        self.assertIn('SAFE', result.stdout)


if __name__ == '__main__':
    unittest.main()
