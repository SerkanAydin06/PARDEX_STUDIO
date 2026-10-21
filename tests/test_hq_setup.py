"""Kurulum screen: zero-token status checks, allow-listed install commands, visible provider logins."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import core  # noqa: E402
import hq_setup as setup  # noqa: E402


def fake_env(tools, outputs):
    """tools: names on PATH; outputs: argv-prefix tuple -> (code, text)."""
    def which(name):
        return f'/bin/{name}' if name in tools else None

    def run(argv, timeout=20):
        key = tuple(Path(argv[0]).name if i == 0 else a for i, a in enumerate(argv))
        for prefix, result in outputs.items():
            if key[:len(prefix)] == prefix:
                return result
        return 0, ''
    return mock.patch.object(core, 'which', side_effect=which), mock.patch.object(setup, '_run', side_effect=run)


class SetupStatusTests(unittest.TestCase):
    def setUp(self):
        setup._CACHE['data'] = None
        setup.JOBS.clear()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        for p in (mock.patch.object(setup.Path, 'home', return_value=self.home),
                  mock.patch.object(core, 'HOME', self.home / 'studio')):  # isolated "Test et" results
            p.start()
            self.addCleanup(p.stop)

    def status(self, tools, outputs):
        w, r = fake_env(tools, outputs)
        with w, r:
            return setup.status(force=True)

    def test_empty_machine_points_to_git_first(self):
        s = self.status(set(), {})
        self.assertFalse(s['ready'])
        self.assertIn('Git', s['next'])
        by = {i['key']: i for i in s['items']}
        self.assertEqual(by['git']['actions'], ['install'])
        self.assertEqual(by['claude']['actions'], [])  # cannot install CLIs before Node/npm
        self.assertIn('Node.js', by['claude']['detail'])

    def test_old_node_is_not_ok(self):
        s = self.status({'git', 'node', 'npm'}, {('node', '--version'): (0, 'v18.19.0')})
        node = [i for i in s['items'] if i['key'] == 'node'][0]
        self.assertFalse(node['ok'])
        self.assertIn('en az 20', node['detail'])

    def test_login_states_and_ready_needs_two_ai(self):
        out = {('node', '--version'): (0, 'v22.11.0'),
               ('claude', 'auth', 'status'): (0, json.dumps({'loggedIn': True, 'subscriptionType': 'pro'})),
               ('codex', 'login', 'status'): (1, 'Not logged in')}
        s = self.status({'git', 'node', 'npm', 'claude', 'codex'}, out)
        by = {i['key']: i for i in s['items']}
        self.assertEqual((by['claude']['login'], by['codex']['login']), ('yes', 'no'))
        self.assertIn('pro', by['claude']['detail'])
        self.assertEqual(by['codex']['actions'], ['login', 'update'])
        self.assertFalse(s['ready'])
        self.assertIn('Giriş yap: Codex', s['next'])
        out[('codex', 'login', 'status')] = (0, 'Logged in using ChatGPT')
        self.assertTrue(self.status({'git', 'node', 'npm', 'claude', 'codex'}, out)['ready'])

    def test_gemini_never_claims_a_login_it_cannot_see(self):
        out = {('node', '--version'): (0, 'v22.11.0')}
        g = [i for i in self.status({'git', 'node', 'npm', 'gemini'}, out)['items'] if i['key'] == 'gemini'][0]
        self.assertEqual(g['login'], 'unknown')  # no auth method chosen: Gemini cannot run at all
        (self.home / '.gemini').mkdir()
        (self.home / '.gemini' / 'settings.json').write_text('{"security":{"auth":{"selectedType":"oauth-personal"}}}')
        s = self.status({'git', 'node', 'npm', 'gemini', 'claude'}, {**out, ('claude', 'auth', 'status'): (0, '{"loggedIn":true}')})
        g = [i for i in s['items'] if i['key'] == 'gemini'][0]
        self.assertEqual(g['login'], 'unknown')
        self.assertIn('verify', g['actions'])
        self.assertFalse(s['ready'])  # an unconfirmed login never counts as ready
        self.assertIn('Test et', s['next'])
        (self.home / '.gemini' / 'settings.json').unlink()
        (self.home / '.gemini').mkdir(exist_ok=True)
        (self.home / '.gemini' / 'oauth_creds.json').write_text('{}')
        g = [i for i in self.status({'git', 'node', 'npm', 'gemini'}, out)['items'] if i['key'] == 'gemini'][0]
        self.assertEqual(g['login'], 'unknown')

    def test_status_never_runs_a_prompt(self):
        calls = []
        w, _ = fake_env({'git', 'node', 'npm', 'claude', 'codex', 'gemini'}, {})
        with w, mock.patch.object(setup, '_run', side_effect=lambda argv, timeout=20: calls.append(argv) or (0, 'v22.0.0')):
            setup.status(force=True)
        allowed = {('--version',), ('auth', 'status', '--json'), ('login', 'status')}
        self.assertTrue(all(tuple(a[1:]) in allowed for a in calls), calls)


class SetupActionTests(unittest.TestCase):
    def setUp(self):
        setup.JOBS.clear()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        for p in (mock.patch.object(core, 'HOME', root),
                  mock.patch.object(core, 'STATE', root / 'state.json'),
                  mock.patch.object(setup.store, 'DATABASE', root / 'hq.db')):
            p.start()
            self.addCleanup(p.stop)

    def test_install_commands_are_fixed_official_packages(self):
        w, _ = fake_env({'npm', 'winget'}, {})
        with w:
            self.assertEqual(setup.install_command('codex')[1:], ['install', '-g', '@openai/codex@latest'])
            self.assertIsNone(setup.install_command('gemini'))  # non-Windows: official manual instructions
            with mock.patch.object(setup.os, 'name', 'nt'):
                self.assertEqual(setup.install_command('git')[1:4], ['install', '--id', 'Git.Git'])
        with self.assertRaises(ValueError):
            setup.install('rm -rf /')

    def test_install_runs_once_in_background_and_reports(self):
        w, _ = fake_env({'npm'}, {})
        with w, mock.patch.object(setup, '_run', return_value=(0, 'added 1 package')) as run:
            out = setup.install('claude')
            for _ in range(50):
                if setup.JOBS['claude']['state'] != 'running':
                    break
                import time
                time.sleep(0.02)
        self.assertEqual(out['started'], 'claude')
        self.assertEqual(setup.JOBS['claude']['state'], 'ok')
        self.assertEqual(run.call_args.args[0][-1], '@anthropic-ai/claude-code@latest')

    def test_base_tool_without_winget_gives_download_page(self):
        w, _ = fake_env(set(), {})
        with w:
            out = setup.install('node')
        self.assertTrue(out['manual'])
        self.assertIn('nodejs.org', out['url'])

    def test_login_opens_visible_window_with_fixed_command(self):
        opened = []
        w, _ = fake_env({'codex'}, {})
        with w, mock.patch.object(setup.os, 'name', 'nt'):
            out = setup.login('codex', opener=lambda cmd, env=None: opened.append(cmd))
        self.assertTrue(out['opened'])
        self.assertEqual(opened[0][:3], ['cmd.exe', '/c', 'start'])
        self.assertEqual(opened[0][-2:], ['codex', 'login'])
        w, _ = fake_env(set(), {})
        with w, self.assertRaises(ValueError):
            setup.login('claude')

    def test_verify_records_result_and_counts_only_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(core, 'HOME', Path(tmp)):
            w, _ = fake_env({'gemini'}, {})
            with w, mock.patch.object(setup, '_run', return_value=(41, 'Please set an Auth method')):
                out = setup.verify('gemini')
            self.assertFalse(out['ok'])
            self.assertIn('Giriş doğrulanamadı', out['message'])
            with w, mock.patch.object(setup, '_run', return_value=(0, 'OK')) as run:
                self.assertTrue(setup.verify('gemini')['ok'])
            self.assertEqual(run.call_args.args[0][1], '-p')
            self.assertEqual(setup._gemini_login('gemini')[0], 'yes')
        with self.assertRaises(ValueError):
            setup.verify('claude')

    def test_verify_rejects_substrings_and_records_attempts(self):
        with mock.patch.object(core, 'which', return_value='/fake/gemini'):
            for output in ('TOKEN unavailable', 'NOT OK', 'OK extra', 'ok'):
                with self.subTest(output=output), mock.patch.object(setup, '_run', return_value=(0, output)):
                    self.assertFalse(setup.verify('gemini')['ok'])
        self.assertEqual(setup.store.calls_used(path=setup.store.DATABASE), 4)
        self.assertEqual(core.usage_count(), 4)

    def test_verify_honors_pause_budget_and_strict_mode(self):
        with mock.patch.object(core, 'which', return_value='/fake/gemini'), mock.patch.object(setup, '_run') as run:
            setup.store.update_settings({'paused': True})
            with self.assertRaises(ValueError):
                setup.verify('gemini')
            setup.store.update_settings({'paused': False, 'day_call_limit': 0})
            with self.assertRaises(ValueError):
                setup.verify('gemini')
            setup.store.update_settings({'day_call_limit': 40})
            with mock.patch.dict(setup.os.environ, {'PARDEX_REQUIRE_ISOLATED_AI': '1'}):
                with self.assertRaises(RuntimeError):
                    setup.verify('gemini')
            run.assert_not_called()
        self.assertEqual(core.usage_count(), 0)

    def test_copilot_verification_uses_clean_output_and_reports_failures(self):
        with mock.patch.object(core, 'which', return_value='/fake/copilot'):
            with mock.patch.object(setup, '_run', return_value=(0, 'OK')) as run:
                self.assertTrue(setup.verify('copilot')['ok'])
                self.assertIn('--silent', run.call_args.args[0])
                self.assertIn('--no-ask-user', run.call_args.args[0])
            for code, text in ((1, 'Quota exceeded'), (127, 'OSError'),
                               (0, 'OK\nTotal usage: 1 request')):
                with self.subTest(text=text), mock.patch.object(setup, '_run', return_value=(code, text)):
                    result = setup.verify('copilot')
                    self.assertFalse(result['ok'])
                    self.assertEqual(result['exit_code'], code)
                    self.assertEqual(result['detail'], text)
                    self.assertNotIn('hesabına bağlan', result['message'])

    def test_old_verification_is_historical_evidence_not_logout(self):
        core.save_json(core.HOME / 'hq' / 'setup_verified.json',
                       {'copilot': {'ok': True, 'checked_at': 0}})
        self.assertEqual(setup._copilot_login('unused')[0], 'cached')

    def test_connection_test_uses_quality_budget_and_preserves_success(self):
        setup.store.update_settings({'budgets': {'ceo': 0}})
        with mock.patch.object(core, 'which', return_value='/fake/agy'):
            with mock.patch.object(setup, '_run', return_value=(0, 'OK')):
                self.assertTrue(setup.verify('gemini')['ok'])
            self.assertEqual(setup.store.calls_used('ceo'), 0)
            self.assertEqual(setup.store.calls_used('kalite'), 1)
            with mock.patch.object(setup, '_run', return_value=(1, 'Network unavailable')):
                self.assertFalse(setup.verify('gemini')['ok'])
            self.assertEqual(setup._gemini_login('unused')[0], 'yes')
            with mock.patch.object(setup, '_run', return_value=(1, 'Not signed in')):
                setup.verify('gemini')
            self.assertEqual(setup._gemini_login('unused')[0], 'unknown')

    def test_old_setup_calls_are_reclassified_not_deleted(self):
        setup.store.record('ceo', 'ai_call', 1, 'Gemini', note='Kurulum giriş testi')
        setup.store.record('ceo', 'ai_call', 1, 'Claude', note='CEO planı')
        self.assertEqual(setup.store.calls_used('ceo'), 1)
        self.assertEqual(setup.store.calls_used('kalite'), 1)
        self.assertEqual(setup.store.calls_used(), 2)

    def test_server_routes_are_allow_listed(self):
        import re
        import hq_server
        src = Path(hq_server.__file__).read_text(encoding='utf-8')
        pattern = re.search(r"/api/setup/\(install\|login\|verify\)/\(([^)]*)\)", src).group(1)
        self.assertEqual(set(pattern.split('|')), {'git', 'node', 'gh', 'claude', 'codex', 'gemini', 'copilot'})

    def test_copilot_is_optional_and_only_trusted_after_test(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(core, 'HOME', Path(tmp)):
            setup._CACHE['data'] = None
            out = {('node', '--version'): (0, 'v22.11.0'),
                   ('claude', 'auth', 'status'): (0, '{"loggedIn": true}')}
            w, r = fake_env({'git', 'node', 'npm', 'claude'}, out)
            with w, r:
                s = setup.status(force=True)
            cop = [i for i in s['items'] if i['key'] == 'copilot'][0]
            self.assertTrue(cop['optional'])
            self.assertNotIn('Copilot', s['next'])  # never nags to install an optional tool
            w, r = fake_env({'git', 'node', 'npm', 'claude', 'copilot'}, out)
            with w, r:
                cop = [i for i in setup.status(force=True)['items'] if i['key'] == 'copilot'][0]
            self.assertEqual((cop['login'], cop['actions'][0]), ('unknown', 'verify'))
            with fake_env({'copilot'}, {})[0], mock.patch.object(setup, '_run', return_value=(1, "Start 'copilot' and run the '/login' command")):
                self.assertFalse(setup.verify('copilot')['ok'])
            self.assertEqual(setup._copilot_login('copilot')[0], 'unknown')
            with fake_env({'copilot'}, {})[0]:
                setup.login('copilot')  # new login: stale "no" is forgotten (non-Windows path: no window opened)
            self.assertEqual(setup._copilot_login('copilot')[0], 'unknown')
            with fake_env({'copilot'}, {})[0], mock.patch.object(setup, '_run', return_value=(0, 'OK')):
                self.assertTrue(setup.verify('copilot')['ok'])
            w, r = fake_env({'git', 'node', 'npm', 'claude', 'copilot'}, out)
            with w, r:
                self.assertTrue(setup.status(force=True)['ready'])  # Claude + verified Copilot = two AIs

    def test_subscription_login_is_not_replaced_by_tokens(self):
        with mock.patch.dict(setup.os.environ, {'GH_TOKEN': 'x', 'COPILOT_GITHUB_TOKEN': 'y', 'ANTHROPIC_API_KEY': 'z'}):
            env = setup._env()
        self.assertFalse({'GH_TOKEN', 'COPILOT_GITHUB_TOKEN', 'ANTHROPIC_API_KEY'} & set(env))


if __name__ == '__main__':
    unittest.main()
