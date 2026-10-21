"""Phase 4 — project line, router and Ar-Ge. Fake AI and fake engine tests; no network, no real CLI."""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import core  # noqa: E402
import hq_projects as hp  # noqa: E402
import hq_research as hr  # noqa: E402
import hq_router as router  # noqa: E402
import hq_store as store  # noqa: E402

SPEC = {'reply': 'Tamam, tarif hazır.', 'ready': True, 'complexity': 'Orta',
        'spec': {'name': 'Yıldız Toplayıcı', 'summary': 'Uzay gemisiyle yıldız toplanan 2D oyun', 'engine': 'web',
                 'platform': 'tarayıcı', 'features': ['Gemi hareketi', 'Yıldız toplama ve skor', 'Oyun sonu ekranı'],
                 'acceptance': ['Ok tuşlarıyla gemi hareket eder', 'Yıldız alınca skor artar']}}


class FakeAI:
    """Scripted company: CEO splits in 2, implementer writes a file, reviewer fails once then passes."""

    def __init__(self, review_script=('FAIL', 'PASS', 'PASS')):
        self.calls, self.review = [], list(review_script)

    def __call__(self, role, prompt, cwd, dept, **kw):
        self.calls.append((role, dept, kw.get('avoid', ())))
        prov = {'review': 'Gemini'}.get(role, 'Codex')
        if role == 'plan_chat':
            out = json.dumps(SPEC, ensure_ascii=False)
        elif role in ('breakdown', 'architect'):
            out = json.dumps({'packages': [{'title': 'İskelet ve canvas', 'detail': 'index.html + main.js'},
                                           {'title': 'Yıldız ve skor', 'detail': 'skor sayacı'}]})
        elif role in ('implement', 'fix', 'fix_strong'):
            (Path(cwd) / f'part{len(self.calls)}.js').write_text('// kod\n')
            out = 'yazdım\nPARDEX_DONE=Parça eklendi'
        elif role == 'review':
            v = self.review.pop(0) if self.review else 'PASS'
            out = f'inceleme\nPARDEX_QA_VERDICT={v}\nPARDEX_QA_FINDINGS=' + ('Skor artmıyor, olay bağlanmamış' if v == 'FAIL' else 'Sorun yok, kabul ölçütüne uygun')
        elif role == 'research':
            out = json.dumps({'ideas': [
                {'title': 'Gerçek kaynaklı fikir', 'type': 'urun', 'sources': ['https://a.com/x', 'https://b.org/y'], 'revenue': 4},
                {'title': 'Kaynaksız uydurma fikir', 'type': 'urun', 'sources': []},
                {'title': 'Pahalı araç', 'type': 'uyelik', 'sources': ['https://c.com', 'https://d.com'], 'price': '20 USD/ay'}]})
        else:
            out = 'ok'
        return {'ok': True, 'output': out, 'provider': prov, 'model': 'test', 'effort': '', 'reason': 'test'}


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

    def planned(self, ai):
        p = hp.new_product('Yıldız', 'oyun', self.db)
        hp.chat(p['id'], 'Uzayda yıldız toplanan basit bir web oyunu', self.db, ai=ai)
        return p['id']


class ProjectLineTests(Base):
    def test_full_line_plan_build_fix_deliver(self):
        ai = FakeAI()
        pid = self.planned(ai)
        p = hp.get(pid, self.db)
        self.assertEqual(p['spec']['engine'], 'web')
        self.assertEqual(p['stage'], 'planlama')
        p = hp.start(pid, self.db, ai=ai)
        folder = Path(p['folder'])
        self.assertTrue((folder / '.studio' / 'BRIEF.md').is_file())
        self.assertFalse(hp._inside_company(folder))
        self.assertEqual(len(p['packages']), 2)
        p = hp.run_production(pid, self.db, ai=ai, tester=lambda f: (True, 'Web test: OK'))
        self.assertEqual(p['stage'], 'teslim')
        self.assertTrue(all(k['status'] == 'tamam' for k in p['packages']))
        first = p['packages'][0]
        self.assertEqual(first['attempts'], 1)  # failed once, fixed
        roles = [c[0] for c in ai.calls]
        self.assertIn('fix', roles)
        # reviewer is always asked to avoid the implementer's provider
        self.assertTrue(all(c[2] == ('Codex',) for c in ai.calls if c[0] == 'review'))
        self.assertTrue(store.lessons('oyun', path=self.db))  # learned from the fixed mistake
        self.assertIn('teslim raporu', p['report'])
        self.assertTrue((folder / '.studio' / 'TESLIM.md').is_file())
        if shutil.which('git'):
            log = core.run(['git', 'log', '--oneline'], folder).stdout
            self.assertIn('PARDEX paket 1', log)
        hp.accept(pid, self.db)
        self.assertEqual(hp.get(pid, self.db)['stage'], 'tamamlandi')

    def test_invalid_review_pauses_without_code_fix_and_shows_evidence(self):
        ai = FakeAI()
        pid = self.planned(ai)
        hp.start(pid, self.db, ai=ai)
        def reviewer_failure(role, *args, **kw):
            result = ai(role, *args, **kw)
            if role == 'review':
                result.update(ok=False, output='EPERM: cannot read scripts directory')
            return result
        p = hp.run_production(pid, self.db, ai=reviewer_failure, tester=lambda f: (True, 'OK'))
        self.assertEqual(p['stage'], 'soru')
        self.assertEqual(p['packages'][0]['attempts'], 0)
        self.assertEqual(p['packages'][0]['status'], 'takildi')
        self.assertNotIn('fix', [c[0] for c in ai.calls])
        self.assertTrue(any('EPERM' in c['text'] and 'Gemini' in c['text'] for c in p['chat']))
        self.assertEqual(hp.open_questions(self.db)[0]['kind'], 'qa')

    def test_review_uses_supplied_evidence_without_terminal_permission(self):
        p = {'spec': {'summary': 'Petris', 'acceptance': ['10x20 grid']}}
        k = {'title': 'Grid', 'detail': 'Falling piece'}
        prompt = hp._review_prompt(p, k, '+ grid = Vector2i(10, 20)', True, 'Godot: OK', self.db)
        self.assertIn('+ grid = Vector2i(10, 20)', prompt)
        self.assertIn('Godot: OK', prompt)
        self.assertIn('başka araç çağırma', prompt)
        self.assertIn('PARDEX_QA_UNAVAILABLE=', prompt)
        self.assertIsNone(hp._qa('PARDEX_QA_UNAVAILABLE=Kod farkı eksik, karar verilemiyor'))

    def test_review_evidence_keeps_complete_new_files_and_spaced_paths(self):
        board = 'extends Node\n' + '# board logic\n' * 180 + '# END_BOARD'
        test = 'extends Node\n' + '# assertions\n' * 180 + '# END_TEST'
        (self.root / 'Board.gd').write_text(board)
        (self.root / 'test board.gd').write_text(test)
        def git(folder, *args):
            import subprocess
            output = 'Board.gd\0test board.gd\0' if args[0] == 'ls-files' else ''
            return subprocess.CompletedProcess(args, 0, output)
        with mock.patch.object(hp, '_git', side_effect=git):
            evidence = hp._diff(self.root)
            self.assertIn(board, evidence)
            self.assertIn(test, evidence)
            small = hp._diff(self.root, limit=1000)
            self.assertIn('EKSİK KANIT', small)
            self.assertNotIn('+++ YENİ DOSYA', small)
        report = 'START_ENGINE_LOG' + 'x' * 5000 + 'END_ENGINE_LOG'
        excerpt = hp._evidence_excerpt(report, 4000)
        self.assertTrue(excerpt.startswith('START_ENGINE_LOG'))
        self.assertTrue(excerpt.endswith('END_ENGINE_LOG'))
        self.assertIn('ATLANDI', excerpt)
        self.assertLessEqual(len(excerpt), 4000)

    def test_review_retry_preserves_code_and_only_spends_review_call(self):
        ai = FakeAI()
        pid = self.planned(ai)
        hp.start(pid, self.db, ai=ai)
        def unavailable(role, *args, **kw):
            result = ai(role, *args, **kw)
            if role == 'review':
                result['output'] = 'PARDEX_QA_UNAVAILABLE=HUD sahnesi eksik'
            return result
        p = hp.run_production(pid, self.db, ai=unavailable, tester=lambda f: (True, 'OK'))
        k = p['packages'][0]
        before_calls = p['used_calls']
        before_writes = sum(c[0] in ('implement', 'fix') for c in ai.calls)
        q = hp.open_questions(self.db)[0]
        hp.answer(q['id'], q['options'][0], self.db)
        self.assertEqual(hp.get(pid, self.db)['packages'][0]['status'], 'denetim')
        p = hp.run_production(pid, self.db, ai=unavailable, tester=lambda f: (True, 'OK'))
        self.assertEqual(p['used_calls'], before_calls + 1)
        self.assertEqual(sum(c[0] in ('implement', 'fix') for c in ai.calls), before_writes)
        self.assertEqual(p['packages'][0]['attempts'], k['attempts'])
        self.assertEqual(p['packages'][0]['provider'], k['provider'])

    def test_godot_standalone_tests_are_executed_and_errors_are_not_passed(self):
        import subprocess
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test_board.gd').write_text('extends SceneTree\nfunc _initialize():\n    quit()\n')
        (self.root / 'tests/test_framework.gd').write_text('extends GutTest\n')
        runs = []
        def run(args, *a, **kw):
            runs.append(args)
            return subprocess.CompletedProcess(args, 0, 'SCRIPT ERROR: Assertion failed' if '--script' in args else 'Import complete')
        with mock.patch.object(core, 'find_godot', return_value='godot'), mock.patch.object(core, 'run', side_effect=run):
            ok, report = core.validate(self.root, 'godot')
        self.assertFalse(ok)
        self.assertEqual(len(runs), 2)
        self.assertIn('res://tests/test_board.gd', runs[-1])
        self.assertIn('özel test çalıştırıcısı gerekli', report)
        self.assertIn('Çalıştırılan bağımsız birim testi: 1', report)

    def test_failed_engine_skips_review_and_fix_receives_complete_report(self):
        ai = FakeAI(review_script=('PASS', 'PASS'))
        pid = self.planned(ai)
        hp.start(pid, self.db, ai=ai)
        failure = 'SCRIPT ERROR: invalid typed array res://tests/test_controls.gd:113\n' + 'details\n' * 800 + 'Zaman asimi (60s)'
        results = iter([(True, 'preflight'), (False, failure)])
        seen_fix = []
        def tester(folder):
            return next(results, (True, 'All tests passed'))
        def worker(role, prompt, cwd, dept, **kw):
            if role == 'fix':
                seen_fix.append(prompt)
                self.assertEqual((Path(cwd) / '.studio/LAST_TEST.txt').read_text(), failure)
            return ai(role, prompt, cwd, dept, **kw)
        hp._set(pid, self.db, engine='godot')
        with mock.patch.object(core, 'find_godot', return_value='C:/Godot tools/godot.exe'):
            p = hp.run_production(pid, self.db, ai=worker, tester=tester)
        roles = [c[0] for c in ai.calls]
        start = roles.index('implement')
        self.assertEqual(roles[start:start+3], ['implement', 'fix', 'review'])
        self.assertIn('C:/Godot tools/godot.exe', seen_fix[0])
        self.assertIn('test_controls.gd:113', seen_fix[0])
        self.assertIn('LAST_TEST.txt', seen_fix[0])
        self.assertEqual(p['stage'], 'teslim')

    def test_timeout_retains_original_script_error(self):
        import subprocess
        failure = subprocess.TimeoutExpired(['godot'], 60,
                    output=b'SCRIPT ERROR: invalid typed array test_controls.gd:113')
        with mock.patch.object(core.subprocess, 'run', side_effect=failure):
            result = core.run(['godot'], self.root, timeout=60)
        self.assertEqual(result.returncode, 124)
        self.assertIn('test_controls.gd:113', result.stdout)
        self.assertIn('Zaman asimi', result.stdout)

    def test_safe_save_failure_never_spends_ai_or_fix_attempt(self):
        ai = FakeAI()
        pid = self.planned(ai)
        hp.start(pid, self.db, ai=ai)
        before = len(ai.calls)
        tester = lambda f: (False, 'ERROR: Safe save failed. This may be a permissions problem.')
        p = hp.run_production(pid, self.db, ai=ai, tester=tester)
        self.assertEqual(len(ai.calls), before)
        self.assertEqual(p['packages'][0]['attempts'], 0)
        q = hp.open_questions(self.db)[0]
        self.assertEqual(q['kind'], 'environment')
        hp.answer(q['id'], q['options'][0], self.db)
        hp.run_production(pid, self.db, ai=ai, tester=tester)
        self.assertEqual(len(ai.calls), before)

    def test_maintenance_recovers_engine_before_spending_ai(self):
        ai = FakeAI(review_script=('PASS', 'PASS'))
        pid = self.planned(ai)
        p = hp.start(pid, self.db, ai=ai)
        folder = Path(p['folder'])
        (folder / 'project.godot').write_text('[application]\n')
        (folder / 'export_templates').mkdir()
        calls = []
        def tester(f):
            calls.append(len(ai.calls))
            if (f / 'export_templates').exists():
                return False, "ERROR: Cannot go into subdir 'export_templates'."
            return True, 'Godot tests passed'
        p = hp.run_production(pid, self.db, ai=ai, tester=tester)
        self.assertEqual(p['stage'], 'teslim')
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(p['packages'][0]['attempts'], 0)
        self.assertFalse(hp.open_questions(self.db))

    def test_unsuccessful_maintenance_retest_does_not_loop_or_spend_ai(self):
        ai = FakeAI()
        pid = self.planned(ai)
        p = hp.start(pid, self.db, ai=ai)
        folder = Path(p['folder'])
        (folder / 'project.godot').write_text('[application]\n')
        (folder / '.godot/editor').mkdir(parents=True)
        before = len(ai.calls)
        tester = mock.Mock(return_value=(False, 'ERROR: Safe save failed'))
        p = hp.run_production(pid, self.db, ai=ai, tester=tester)
        self.assertEqual(tester.call_count, 2)
        self.assertEqual(len(ai.calls), before)
        q = hp.open_questions(self.db)[0]
        hp.answer(q['id'], q['options'][0], self.db)
        hp.run_production(pid, self.db, ai=ai, tester=tester)
        self.assertEqual(tester.call_count, 3)
        self.assertEqual(len(ai.calls), before)

    def test_test_report_write_denial_preserves_error_in_memory(self):
        with mock.patch.object(hp.maintenance, 'plain_chain', side_effect=PermissionError('denied')):
            result = hp._record_test_report(self.root, 'ERROR: Safe save failed')
        self.assertIn('Safe save failed', result)
        self.assertIn('Rapor dosyasına yazılamadı', result)

    def test_repair_retest_code_error_is_not_an_environment_failure(self):
        ai = FakeAI()
        pid = self.planned(ai)
        p = hp.start(pid, self.db, ai=ai)
        folder = Path(p['folder'])
        (folder / 'project.godot').write_text('[application]\n')
        (folder / '.godot/editor').mkdir(parents=True)
        tester = mock.Mock(side_effect=[(False, 'ERROR: Safe save failed'),
                                       (False, 'SCRIPT ERROR: Unknown identifier')])
        ok, output = hp._test_with_maintenance(pid, folder, tester, self.db)
        self.assertFalse(ok)
        self.assertFalse(hp._test_environment_error(output))
        self.assertIn('Unknown identifier', output)

    def test_review_envelopes_and_duplicate_verdicts(self):
        good = 'PARDEX_QA_VERDICT=PASS\nPARDEX_QA_FINDINGS=Sorun yok, kabul ölçütüne uygun'
        self.assertEqual(hp._qa(json.dumps({'status': 'SUCCESS', 'response': good}))[0], 'PASS')
        self.assertEqual(hp._qa('```text\n' + good + '\n```')[0], 'PASS')
        self.assertIsNone(hp._qa('PARDEX_QA_VERDICT=FAIL\n' + good))
        self.assertIsNone(hp._qa(json.dumps({'status': 'ERROR', 'response': good})))

    def test_untested_engine_asks_owner_once(self):
        ai = FakeAI(review_script=('PASS', 'PASS'))
        pid = self.planned(ai)
        hp.start(pid, self.db, ai=ai)
        no_engine = lambda f: (False, 'Godot kurulu/bulunur degil. Test yapilmadi.')
        p = hp.run_production(pid, self.db, ai=ai, tester=no_engine)
        self.assertEqual(p['stage'], 'soru')
        q = hp.open_questions(self.db)[0]
        self.assertEqual(q['kind'], 'untested')
        self.assertNotIn('implement', [c[0] for c in ai.calls])  # asked before spending tokens
        hp.answer(q['id'], q['options'][0], self.db)
        p = hp.run_production(pid, self.db, ai=ai, tester=no_engine)
        self.assertEqual(p['stage'], 'teslim')

    def test_stuck_package_escalates_and_skip(self):
        ai = FakeAI(review_script=('FAIL',) * 10)
        pid = self.planned(ai)
        hp.start(pid, self.db, ai=ai)
        p = hp.run_production(pid, self.db, ai=ai, tester=lambda f: (True, 'OK'))
        self.assertEqual(p['stage'], 'soru')
        q = hp.open_questions(self.db)[0]
        self.assertEqual(q['kind'], 'stuck')
        impl = [c for c in ai.calls if c[0] in ('implement', 'fix')]
        self.assertEqual(len(impl), 1 + hp.MAX_FIXES)
        self.assertEqual(impl[-1][2], ('Codex',))  # last fix tried by another team member
        hp.answer(q['id'], 'Bu paketi atla', self.db)
        self.assertEqual(hp.get(pid, self.db)['packages'][0]['status'], 'atlandi')

    def test_budget_stop_is_a_question(self):
        ai = FakeAI(review_script=('PASS',) * 5)
        pid = self.planned(ai)
        hp.start(pid, self.db, ai=ai)
        hp._set(pid, self.db, approved_calls=1)
        p = hp.run_production(pid, self.db, ai=ai, tester=lambda f: (True, 'OK'))
        self.assertEqual(hp.open_questions(self.db)[0]['kind'], 'budget')
        self.assertEqual(p['stage'], 'soru')

    def test_start_requires_ready_plan_and_outside_repo(self):
        p = hp.new_product('Boş', 'uygulama', self.db)
        with self.assertRaises(ValueError):
            hp.start(p['id'], self.db, ai=FakeAI())
        with self.assertRaises(ValueError):
            store.update_settings({'projects_root': str(core.BASE / 'icerde')}, self.db)

    def test_owner_change_request_reopens_production(self):
        ai = FakeAI(review_script=('PASS',) * 6)
        pid = self.planned(ai)
        hp.start(pid, self.db, ai=ai)
        hp.run_production(pid, self.db, ai=ai, tester=lambda f: (True, 'OK'))
        p = hp.request_changes(pid, 'Gemi biraz daha hızlı olsun', self.db)
        self.assertEqual(p['stage'], 'uretim')
        p = hp.run_production(pid, self.db, ai=ai, tester=lambda f: (True, 'OK'))
        self.assertEqual(p['stage'], 'teslim')
        self.assertEqual(len(p['packages']), 3)


class RouterTests(Base):
    def test_choose_respects_install_override_and_learning(self):
        have = {'Claude': 'claude', 'Gemini': 'gemini', 'Codex': 'codex'}
        self.assertEqual(router.choose('implement', path=self.db, have=have)[0], 'Codex')
        self.assertEqual(router.choose('review', avoid=('Gemini',), path=self.db, have=have)[0], 'Claude')
        self.assertEqual(router.choose('implement', path=self.db, have={'Claude': 'c'})[:2], ('Claude', 'sonnet'))
        for _ in range(6):
            store.route_result('implement', 'Codex', False, self.db)
            store.route_result('implement', 'Claude', True, self.db)
        p, _, _, why = router.choose('implement', path=self.db, have=have)
        self.assertEqual(p, 'Claude')
        self.assertIn('Öğrenme', why)
        store.update_settings({'routing': {'implement': {'provider': 'Gemini', 'model': 'pro', 'effort': ''}}}, self.db)
        self.assertEqual(router.choose('implement', path=self.db, have=have)[0], 'Gemini')
        with self.assertRaises(RuntimeError):
            router.choose('implement', path=self.db, have={})

    def test_commands_are_scoped(self):
        with mock.patch.object(router, '_supports', return_value=True):
            w = router.build_cmd('Claude', 'claude', 'sonnet', 'medium', 'write')
            r = router.build_cmd('Claude', 'claude', 'haiku', 'low', 'read')
        self.assertIn('acceptEdits', w)
        self.assertNotIn('Bash', ' '.join(w))
        self.assertIn('dontAsk', r)
        self.assertIn('read-only', router.build_cmd('Codex', 'codex', '', 'low', 'read'))
        self.assertNotIn('yolo', ' '.join(router.build_cmd('Gemini', 'gemini', 'pro', '', 'write')))

    def test_gemini_zero_exit_permission_denial_is_not_success(self):
        import subprocess
        notice = 'jetski: no output produced — a tool required the "command" permission that headless mode cannot prompt for'
        fake = lambda *a, **kw: subprocess.CompletedProcess(a, 0, notice)
        out = router.call('review', 'review evidence', self.root, 'kalite',
                          path=self.db, runner=fake, have={'Gemini': 'agy'})
        self.assertFalse(out['ok'])
        self.assertIn('headless', out['output'])

    def test_call_records_budget_and_stops(self):
        fake = mock.Mock(return_value=mock.Mock(returncode=0, stdout='cevap'))
        out = router.call('text', 'merhaba', self.root, 'medya', path=self.db, runner=fake, have={'Claude': 'claude'})
        self.assertTrue(out['ok'])
        self.assertEqual(store.calls_used('medya', path=self.db), 1)
        store.update_settings({'paused': True}, self.db)
        with self.assertRaises(router.BudgetStop):
            router.call('text', 'x', self.root, 'medya', path=self.db, runner=fake, have={'Claude': 'claude'})


class ResearchTests(Base):
    def test_only_source_backed_ideas_survive(self):
        out = hr.research('oyun', 'mobil', self.db, ai=FakeAI(), check=lambda u: True)
        titles = [a['title'] for a in out['accepted']]
        self.assertIn('Gerçek kaynaklı fikir', titles)
        self.assertNotIn('Kaynaksız uydurma fikir', titles)
        member = [i for i in store.ideas(self.db) if i['title'].startswith('[Üyelik önerisi]')][0]
        self.assertEqual(member['stage'], 'onay')  # owner decides, nothing bought
        again = hr.research('oyun', '', self.db, ai=FakeAI(), check=lambda u: True)
        self.assertFalse(again['accepted'])  # duplicates rejected

    def test_unreachable_sources_rejected(self):
        out = hr.research('uygulama', '', self.db, ai=FakeAI(), check=lambda u: False)
        self.assertFalse(out['accepted'])


class ServerFlowTests(Base):
    def test_product_flow_over_http(self):
        import threading, time, urllib.request
        import hq_server
        from http.server import ThreadingHTTPServer
        panel = hq_server.Panel(db=self.db, token='K' * 20, ai=FakeAI(('PASS',) * 6), tester=lambda f: (True, 'OK'))
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), hq_server.make_handler(panel))
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        base = f'http://127.0.0.1:{httpd.server_address[1]}'

        def post(p, b):
            r = urllib.request.Request(base + p, data=json.dumps(b).encode(),
                                       headers={'Content-Type': 'application/json', 'X-PARDEX-Token': 'K' * 20})
            return json.loads(urllib.request.urlopen(r, timeout=10).read())['data']

        def get(p):
            r = urllib.request.Request(base + p, headers={'X-PARDEX-Token': 'K' * 20})
            return json.loads(urllib.request.urlopen(r, timeout=10).read())
        pid = post('/api/product', {'name': 'Not Defteri', 'kind': 'uygulama'})['id']
        post(f'/api/product/{pid}/chat', {'text': 'Basit web not defteri'})
        post(f'/api/product/{pid}/start', {})
        for _ in range(100):
            if get(f'/api/product/{pid}')['stage'] == 'teslim':
                break
            time.sleep(0.05)
        self.assertEqual(get(f'/api/product/{pid}')['stage'], 'teslim')
        self.assertEqual(get('/api/products')[0]['id'], pid)
        self.assertIn('rows', get('/api/routing'))


if __name__ == '__main__':
    unittest.main()
