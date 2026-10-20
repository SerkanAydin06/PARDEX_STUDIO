"""Phase 5 — data-driven organisation, Yönetim Kurulu, health report and stage hooks. No real AI."""
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
import hq_board as board  # noqa: E402
import hq_org as org  # noqa: E402
import hq_projects as hp  # noqa: E402
import hq_store as store  # noqa: E402
from tests.test_hq_projects import FakeAI  # noqa: E402

TASARIM = {'op': 'add_department', 'key': 'tasarim', 'name': 'Tasarım', 'mission': 'Oyun ve arayüz tasarım raporu yazar',
           'tier': 'K1', 'budget': 6, 'hook': 'plan_sonrasi', 'mode': 'rapor'}


class Base(unittest.TestCase):
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


class OrgTests(Base):
    def test_seed_and_add_department_with_version_and_rollback(self):
        d = org.departments(self.db)
        self.assertEqual(len(d), len(store.DEPARTMENTS))
        self.assertTrue(d['kalite']['required'])
        vid = org.apply([TASARIM], 'Tasarım ekibi', path=self.db)
        self.assertIn('tasarim', store.depts(self.db))
        self.assertEqual(store.settings(self.db)['budgets']['tasarim'], 6)
        self.assertEqual([h['key'] for h in org.hooks('plan_sonrasi', self.db)], ['tasarim'])
        store.record('tasarim', 'ai_call', 1, 'X', path=self.db)  # new dept is a real cost centre
        org.apply([{'op': 'set_workflow', 'field': 'max_fixes', 'value': 3}], path=self.db)
        self.assertEqual(org.workflow(self.db)['max_fixes'], 3)
        out = org.rollback(vid, self.db)
        self.assertEqual(out['also_undone'], 1)
        self.assertNotIn('tasarim', store.depts(self.db))
        self.assertEqual(org.workflow(self.db)['max_fixes'], 2)

    def test_validation_blocks_unsafe_and_broken_changes(self):
        bad = [
            [{'op': 'deactivate_department', 'key': 'kalite'}],
            [{'op': 'update_department', 'key': 'oyun', 'prompt': 'Onay olmadan git push et'}],
            [dict(TASARIM, hook='paket_sonrasi', mode='rapor')],
            [dict(TASARIM, tier='K0')],
            [{'op': 'set_workflow', 'field': 'kind_dept', 'value': {'oyun': 'yok'}}],
            [{'op': 'set_workflow', 'field': 'max_fixes', 'value': 9}],
            [{'op': 'drop_table'}],
            [{'op': 'update_department', 'key': 'kalite', 'hook': 'paket_sonrasi', 'mode': 'denetim'}],
        ]
        for ops in bad:
            with self.assertRaises(ValueError, msg=ops):
                org.apply(ops, path=self.db)
        self.assertEqual(org.versions(path=self.db), [])

    def test_all_or_nothing(self):
        with self.assertRaises(ValueError):
            org.apply([TASARIM, {'op': 'set_budget', 'key': 'yok', 'budget': 3}], path=self.db)
        self.assertNotIn('tasarim', store.depts(self.db))

    def test_production_can_move_to_new_department(self):
        org.apply([{'op': 'add_department', 'key': 'mobil', 'name': 'Mobil Ekip', 'mission': 'Mobil uygulama kodu yazar',
                    'tier': 'K2', 'budget': 30},
                   {'op': 'set_workflow', 'field': 'kind_dept', 'value': {'uygulama': 'mobil'}}], path=self.db)
        with self.assertRaises(ValueError):
            org.apply([{'op': 'deactivate_department', 'key': 'mobil'}], path=self.db)
        ai = FakeAI(('PASS',) * 6)
        p = hp.new_product('Not', 'uygulama', self.db)
        hp.chat(p['id'], 'web not uygulaması', self.db, ai=ai)
        p = hp.start(p['id'], self.db, ai=ai)
        self.assertTrue(all(k['dept'] == 'mobil' for k in p['packages']))


class HookTests(Base):
    def run_line(self, ai):
        p = hp.new_product('Yıldız', 'oyun', self.db)
        hp.chat(p['id'], 'web oyunu', self.db, ai=ai)
        hp.start(p['id'], self.db, ai=ai)
        return hp.run_production(p['id'], self.db, ai=ai, tester=lambda f: (True, 'OK'))

    def test_plan_hook_report_is_fed_to_team(self):
        org.apply([TASARIM], path=self.db)
        prompts = []
        base = FakeAI(('PASS',) * 6)

        def ai(role, prompt, cwd, dept, **kw):
            prompts.append((role, dept, prompt))
            if dept == 'tasarim':
                return {'ok': True, 'output': 'Renkler: lacivert. Ekran: tek sahne.', 'provider': 'Claude', 'model': 'haiku',
                        'effort': 'low', 'reason': ''}
            return base(role, prompt, cwd, dept, **kw)
        p = self.run_line(ai)
        self.assertEqual(p['stage'], 'teslim')
        self.assertTrue((Path(p['folder']) / '.studio' / 'DEPT_tasarim.md').is_file())
        impl = [x for x in prompts if x[0] == 'implement']
        self.assertTrue(impl and all('lacivert' in x[2] for x in impl))
        self.assertEqual([x[0] for x in prompts if x[1] == 'tasarim'], ['text'])  # K1 report -> cheapest role

    def test_package_audit_hook_can_fail_and_second_reviewer(self):
        org.apply([{'op': 'add_department', 'key': 'guvenlik', 'name': 'Güvenlik', 'mission': 'Her pakette güvenlik denetimi',
                    'tier': 'K1', 'budget': 20, 'hook': 'paket_sonrasi', 'mode': 'denetim'},
                   {'op': 'set_workflow', 'field': 'reviews', 'value': 2},
                   {'op': 'add_department', 'key': 'dokuman', 'name': 'Dokümantasyon', 'mission': 'Teslim öncesi kullanım kılavuzu yazar',
                    'tier': 'K1', 'budget': 4, 'hook': 'teslim_oncesi', 'mode': 'rapor'}], path=self.db)
        audits = {'n': 0}
        base = FakeAI(('PASS',) * 20)
        reviews = []

        def ai(role, prompt, cwd, dept, **kw):
            if dept == 'guvenlik':
                audits['n'] += 1
                v = 'FAIL' if audits['n'] == 1 else 'PASS'
                return {'ok': True, 'output': f'x\nPARDEX_QA_VERDICT={v}\nPARDEX_QA_FINDINGS=Girdi doğrulaması eksik, düzelt',
                        'provider': 'Claude', 'model': 'haiku', 'effort': '', 'reason': ''}
            if dept == 'dokuman':
                return {'ok': True, 'output': 'KILAVUZ: oklarla oyna', 'provider': 'Claude', 'model': 'haiku', 'effort': '', 'reason': ''}
            if role == 'review':
                reviews.append(kw.get('avoid'))
            return base(role, prompt, cwd, dept, **kw)
        p = self.run_line(ai)
        self.assertEqual(p['stage'], 'teslim')
        self.assertEqual(p['packages'][0]['attempts'], 1)  # security audit failure triggered a fix
        self.assertIn(('Codex', 'Gemini'), reviews)  # second reviewer avoids maker and first reviewer
        self.assertIn('KILAVUZ', p['report'])

    def test_workflow_max_fixes_is_respected(self):
        org.apply([{'op': 'set_workflow', 'field': 'max_fixes', 'value': 1}], path=self.db)
        ai = FakeAI(('FAIL',) * 10)
        p = self.run_line(ai)
        self.assertEqual(p['stage'], 'soru')
        self.assertEqual(len([c for c in ai.calls if c[0] in ('implement', 'fix')]), 2)


class BoardTests(Base):
    def gmy(self, payload):
        return lambda role, prompt, cwd, dept, **kw: {'ok': True, 'output': json.dumps(payload, ensure_ascii=False),
                                                       'provider': 'Claude', 'model': 'sonnet', 'effort': 'low', 'reason': ''}

    def test_gmy_proposal_needs_owner_approval(self):
        out = board.message('Tasarım departmanı kur, her projede önce o çalışsın', self.db,
                            ai=self.gmy({'reply': 'Tasarım ekibini kuruyorum.', 'summary': 'Tasarım departmanı',
                                         'ops': [TASARIM], 'impact': 'Proje başına +1 K1 çağrı'}))
        prop = out['proposal']
        self.assertEqual(prop['status'], 'bekliyor')
        self.assertNotIn('tasarim', store.depts(self.db))  # nothing changes before approval
        self.assertIn('Yeni departman: Tasarım', prop['lines'][0])
        board.approve(prop['id'], self.db)
        self.assertIn('tasarim', store.depts(self.db))
        with self.assertRaises(ValueError):
            board.approve(prop['id'], self.db)
        self.assertEqual(len(board.chat_log(path=self.db)), 3)

    def test_invalid_gmy_ops_never_become_proposals(self):
        out = board.message('Kalite ekibini kapat', self.db,
                            ai=self.gmy({'reply': 'Kapatıyorum', 'ops': [{'op': 'deactivate_department', 'key': 'kalite'}]}))
        self.assertIsNone(out['proposal'])
        self.assertIn('çekirdek', out['error'])
        self.assertEqual(board.proposals(path=self.db), [])

    def test_question_only_and_reject(self):
        out = board.message('Bu hafta kaç çağrı kullandık?', self.db, ai=self.gmy({'reply': '0 çağrı.', 'ops': []}))
        self.assertIsNone(out['proposal'])
        p = board.propose([{'op': 'set_budget', 'key': 'arge', 'budget': 12}], 'Ar-Ge bütçesi', 'patron', path=self.db)
        self.assertEqual(board.reject(p['id'], self.db)['status'], 'reddedildi')
        self.assertEqual(store.settings(self.db)['budgets']['arge'], 8)

    def test_health_suggestion_from_real_usage(self):
        for _ in range(8):
            store.record('arge', 'ai_call', 1, 'Gemini', path=self.db)
        h = board.health(self.db)
        idx = next(i for i, s in enumerate(h['suggestions']) if s['ops'][0].get('key') == 'arge' and s['ops'][0]['op'] == 'set_budget')
        prop = board.propose_suggestion(idx, self.db)
        self.assertEqual(prop['source'], 'k0')
        board.approve(prop['id'], self.db)
        self.assertGreater(store.settings(self.db)['budgets']['arge'], 8)

    def test_new_company_gets_no_unused_budget_noise(self):
        h = board.health(self.db)
        self.assertFalse([s for s in h['suggestions'] if 'kullanmadı' in s['text']])

    def test_core_request_uses_existing_pipeline(self):
        import evolution
        cand = self.root / 'cand'
        cand.mkdir()
        with mock.patch.object(evolution, 'create_candidate', return_value=cand), \
                mock.patch.object(evolution, 'info', return_value={'state': 'prepared'}), \
                mock.patch.object(evolution, 'ready_to_export', return_value=False):
            r = board.core_create('Panele yeni bir rapor ekranı ekle', self.db)
            self.assertEqual(r['state'], 'hazirlandi')
            with mock.patch.object(evolution, 'install_approved_candidate', side_effect=ValueError('onay yok')):
                with self.assertRaises(ValueError):
                    board.core_step(r['id'], 'kur', self.db)
        self.assertIn('codex', board.core_requirements())


class ServerTests(Base):
    def test_org_and_board_endpoints(self):
        import threading
        import urllib.request
        import hq_server
        from http.server import ThreadingHTTPServer
        panel = hq_server.Panel(db=self.db, token='Z' * 20)
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), hq_server.make_handler(panel))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        base = f'http://127.0.0.1:{httpd.server_address[1]}'
        h = {'X-PARDEX-Token': 'Z' * 20, 'Content-Type': 'application/json'}
        org_view = json.loads(urllib.request.urlopen(urllib.request.Request(base + '/api/org', headers=h)).read())
        self.assertIn('kalite', org_view['departments'])
        req = urllib.request.Request(base + '/api/org/apply', data=json.dumps({'ops': [TASARIM]}).encode(), headers=h)
        self.assertTrue(json.loads(urllib.request.urlopen(req).read())['data']['version'])
        bv = json.loads(urllib.request.urlopen(urllib.request.Request(base + '/api/board', headers=h)).read())
        self.assertIn('suggestions', bv['health'])


if __name__ == '__main__':
    unittest.main()
