"""Phase 3 — company HQ: store, CEO planner, workers and local web panel. No network, no real AI."""
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import core  # noqa: E402
import hq_ceo as ceo  # noqa: E402
import hq_store as store  # noqa: E402
import hq_workers as workers  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / 'hq.sqlite3'
        self.qdb = self.root / 'queue.sqlite3'
        self.project = self.root / 'Game'
        self.project.mkdir()
        (self.project / 'project.godot').write_text('config_version=5')
        p1 = mock.patch.object(core, 'STATE', self.root / 'state.json')
        p2 = mock.patch.object(workers, 'DELIVERABLES', self.root / 'out')
        for p in (p1, p2):
            p.start()
            self.addCleanup(p.stop)


class StoreTests(Base):
    def test_settings_validation_and_budget(self):
        self.assertFalse(store.settings(self.db)['paused'])
        with self.assertRaises(ValueError):
            store.update_settings({'weekly_call_limit': 9999}, self.db)
        with self.assertRaises(ValueError):
            store.update_settings({'unknown': 1}, self.db)
        with self.assertRaises(ValueError):
            store.update_settings({'budgets': {'medya': -1}}, self.db)
        store.update_settings({'budgets': {'medya': 1}}, self.db)
        self.assertEqual(store.budget_check('medya', 1, self.db), (True, ''))
        store.record('medya', 'ai_call', 1, 'Claude', path=self.db)
        ok, why = store.budget_check('medya', 1, self.db)
        self.assertFalse(ok)
        self.assertIn('bütçe', why)
        store.update_settings({'paused': True}, self.db)
        self.assertFalse(store.budget_check('finans', 0, self.db)[0])

    def test_job_rules(self):
        with self.assertRaises(ValueError):
            store.add_job('finans', 'Rapor hazırla lütfen', 'local', 'K0', 1, path=self.db)
        with self.assertRaises(ValueError):
            store.add_job('medya', 'Senaryo yaz', 'text', 'K1', 5, path=self.db)
        j = store.add_job('oyun', 'Kamera sarsıntısı ekle', 'code', 'K2', 1, project='', path=self.db)
        self.assertEqual(j['status'], 'blocked')
        j = store.add_job('oyun', 'Kamera sarsıntısı ekle', 'code', 'K2', 1, project=str(self.project), path=self.db)
        self.assertEqual(j['status'], 'proposed')
        with self.assertRaises(ValueError):
            store.transition(j['id'], 'approved', 'running', path=self.db)

    def test_idea_score_bounds_and_finance(self):
        self.assertEqual(store.idea_score(5, 1, 1, 5), 100)
        self.assertEqual(store.idea_score(1, 5, 5, 1), 0)
        with self.assertRaises(ValueError):
            store.add_idea('Fikir', revenue=6, path=self.db)
        store.record('buyume', 'income', 100, path=self.db)
        store.record('finans', 'expense', 30, path=self.db)
        f = store.finance_summary(self.db)
        self.assertEqual((f['income'], f['expense'], f['net']), (100, 30, 70))
        d = store.dashboard(self.db)
        self.assertEqual(len(d['departments']), len(store.DEPARTMENTS))
        self.assertTrue(d['briefing'])


class CeoTests(Base):
    def test_forbidden_goal_is_blocked(self):
        out = ceo.create_from_goal('Rakip oyunda anti-cheat aşan aimbot makrosu', '', self.db)
        self.assertEqual([j['status'] for j in out['jobs']], ['blocked'])

    def test_routing_and_cost(self):
        specs = ceo.plan('Fırtına Vadisi oyununa düşman ekle ve tanıtım videosu yap')
        depts = [s['dept'] for s in specs]
        self.assertIn('oyun', depts)
        self.assertIn('medya', depts)
        self.assertIn('kalite', depts)
        self.assertTrue(all(s['est_calls'] <= 1 for s in specs))
        no_project = ceo.create_from_goal('Oyuna düşman ekle', '', self.db)
        self.assertNotIn('kalite', [j['dept'] for j in no_project['jobs']])

    def test_ai_plan_parsing_filters(self):
        text = json.dumps({'jobs': [{'dept': 'medya', 'title': 'Fragman senaryosu yaz', 'kind': 'text'},
                                    {'dept': 'xxx', 'title': 'Bilinmeyen departman', 'kind': 'text'},
                                    {'dept': 'oyun', 'title': 'aimbot ekle hemen', 'kind': 'code'}]})
        specs = ceo.parse_ai_plan('önce açıklama ' + text)
        self.assertEqual([s['dept'] for s in specs], ['medya'])

    def test_ai_plan_uses_one_budgeted_call(self):
        fake = mock.Mock(return_value=(True, '{"jobs":[{"dept":"arge","title":"Pazar araştırması yap","kind":"text"}]}', 'Fake'))
        out = ceo.create_from_goal_ai('Yeni oyun fikirleri bul', '', self.db, caller=fake)
        fake.assert_called_once()
        self.assertEqual(out['jobs'][0]['status'], 'proposed')


class WorkerTests(Base):
    def test_local_idea_job_end_to_end(self):
        j = [x for x in ceo.create_from_goal('Satılabilir bir mini oyun çıkar', '', self.db)['jobs'] if x['dept'] == 'urun'][0]
        with self.assertRaises(ValueError):
            workers.run_job(j['id'], self.db, self.qdb)  # not approved yet
        workers.approve(j['id'], self.db, self.qdb)
        done = workers.run_job(j['id'], self.db, self.qdb)
        self.assertEqual(done['status'], 'delivered')
        self.assertEqual(len(store.ideas(self.db)), 1)
        self.assertEqual(workers.accept(j['id'], self.db, self.qdb)['status'], 'accepted')
        self.assertEqual(store.calls_used(path=self.db), 0)

    def test_text_job_with_fake_ai(self):
        j = workers.add_department_job('medya', 'Fragman senaryosu hazırla', self.db)
        workers.approve(j['id'], self.db, self.qdb)
        ok = workers.run_job(j['id'], self.db, self.qdb, caller=lambda d, p, path=None: (True, 'SENARYO', 'Fake'))
        self.assertEqual(ok['status'], 'delivered')
        self.assertTrue((self.root / 'out' / (j['id'] + '.md')).is_file())
        j2 = workers.add_department_job('medya', 'İkinci senaryo yaz', self.db)
        workers.approve(j2['id'], self.db, self.qdb)
        bad = workers.run_job(j2['id'], self.db, self.qdb, caller=lambda d, p, path=None: (False, 'yok', ''))
        self.assertEqual(bad['status'], 'failed')

    def test_local_quality_results(self):
        for result in (True, False):
            with self.subTest(result=result):
                j = store.add_job('kalite', 'Proje kalite kontrolü', 'local', 'K0', 0,
                                  project=str(self.project), action='tests', path=self.db)
                workers.approve(j['id'], self.db, self.qdb)
                with mock.patch.object(core, 'validate', return_value=(result, 'test raporu')):
                    done = workers.run_job(j['id'], self.db, self.qdb)
                self.assertEqual(done['status'], 'delivered' if result else 'failed')
                self.assertIn('test raporu', done['output'])
                if not result:
                    with self.assertRaises(ValueError):
                        workers.accept(j['id'], self.db, self.qdb)
        j = store.add_job('kalite', 'Projesiz kalite kontrolü', 'local', 'K0', 0,
                          action='tests', path=self.db)
        workers.approve(j['id'], self.db, self.qdb)
        with mock.patch.object(core, 'validate') as validate:
            self.assertEqual(workers.run_job(j['id'], self.db, self.qdb)['status'], 'failed')
            validate.assert_not_called()

    def test_value_error_finishes_job_and_releases_worker(self):
        j = workers.add_department_job('medya', 'Fragman senaryosu hazırla', self.db)
        workers.approve(j['id'], self.db, self.qdb)
        with mock.patch.object(workers, 'call_text', side_effect=ValueError('Geçersiz cevap')):
            done = workers.run_job(j['id'], self.db, self.qdb)
        self.assertEqual(done['status'], 'failed')
        self.assertIn('Geçersiz cevap', done['note'])
        next_job = workers.add_department_job('finans', 'Aylık finans raporu', self.db)
        workers.approve(next_job['id'], self.db, self.qdb)
        self.assertEqual(workers.run_job(next_job['id'], self.db, self.qdb)['status'], 'delivered')

    def test_queue_preflight_preserves_approval(self):
        store.update_settings({'default_project': str(self.project)}, self.db)
        j = workers.add_department_job('oyun', 'Oyuncuya zıplama ekle', self.db)
        workers.approve(j['id'], self.db, self.qdb)
        with mock.patch('task_queue.preview_next', return_value={'ready': False}):
            with self.assertRaises(ValueError):
                workers.run_job(j['id'], self.db, self.qdb)
        self.assertEqual(store.get_job(j['id'], self.db)['status'], 'approved')

    def test_pause_blocks_running(self):
        j = workers.add_department_job('finans', 'Aylık finans raporu', self.db)
        workers.approve(j['id'], self.db, self.qdb)
        store.update_settings({'paused': True}, self.db)
        with self.assertRaises(ValueError):
            workers.run_job(j['id'], self.db, self.qdb)
        self.assertEqual(store.get_job(j['id'], self.db)['status'], 'approved')

    def test_code_job_goes_to_queue_approved(self):
        import task_queue as q
        store.update_settings({'default_project': str(self.project)}, self.db)
        j = workers.add_department_job('oyun', 'Oyuncuya çift zıplama ekle', self.db)
        a = workers.approve(j['id'], self.db, self.qdb)
        self.assertTrue(a['task_id'])
        self.assertEqual(q.get_task(a['task_id'], path=self.qdb)['status'], 'ready')
        self.assertEqual(workers.reject(j['id'], 'vazgeçtim', self.db, self.qdb)['status'], 'rejected')


class ServerTests(Base):
    def setUp(self):
        super().setUp()
        import hq_server
        from http.server import ThreadingHTTPServer
        self.panel = hq_server.Panel(db=self.db, queue_db=self.qdb, token='T' * 20)
        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), hq_server.make_handler(self.panel))
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(self.httpd.server_close)
        self.addCleanup(self.httpd.shutdown)
        self.base = f'http://127.0.0.1:{self.httpd.server_address[1]}'

    def req(self, path, body=None, token='T' * 20, host=None):
        h = {'Content-Type': 'application/json'}
        if token:
            h['X-PARDEX-Token'] = token
        if host:
            h['Host'] = host
        r = urllib.request.Request(self.base + path, data=None if body is None else json.dumps(body).encode(), headers=h)
        try:
            with urllib.request.urlopen(r, timeout=5) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_index_has_token_and_security(self):
        with urllib.request.urlopen(self.base + '/', timeout=5) as res:
            html = res.read().decode()
            self.assertIn('T' * 20, html)
            self.assertIn("frame-ancestors 'none'", res.headers['Content-Security-Policy'])
        self.assertEqual(self.req('/api/dashboard', token='wrong')[0], 403)
        self.assertEqual(self.req('/api/dashboard', host='evil.example')[0], 403)
        self.assertEqual(self.req('/api/goal', {'text': 'Oyun yap'}, token=None)[0], 403)

    def test_goal_flow_over_http(self):
        code, out = self.req('/api/goal', {'text': 'Fırtına Vadisi için tanıtım videosu hazırla'})
        self.assertEqual(code, 200)
        self.assertTrue(out['data']['jobs'])
        code, d = self.req('/api/dashboard')
        self.assertEqual(code, 200)
        self.assertGreaterEqual(d['kpi']['pending'], 1)
        self.assertEqual(self.req('/api/ledger', {'kind': 'ai_call', 'amount': 1})[0], 400)
        self.assertEqual(self.req('/api/nope', {})[0], 400)


if __name__ == '__main__':
    unittest.main()
