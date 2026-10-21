"""Reliability regressions for the project line: no false secret blocks, no silent production lock,
zero-token provider preflight, full asset copies, safe redirect following. Offline, fake AI."""
import shutil
import socket
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
import hq_research as research  # noqa: E402
import hq_router as router  # noqa: E402
import hq_store as store  # noqa: E402
from tests.test_hq_projects import FakeAI  # noqa: E402

GIT = shutil.which('git')


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
        store.update_settings({'projects_root': str(self.root / 'urunler'), 'weekly_call_limit': 500,
                               'day_call_limit': 200}, self.db)

    def started(self, ai):
        p = hp.new_product('Coin', 'oyun', self.db)
        hp.chat(p['id'], 'web oyunu', self.db, ai=ai)
        return hp.start(p['id'], self.db, ai=ai)


@unittest.skipUnless(GIT, 'git not installed')
class CommitTests(Base):
    def repo(self, rel):
        f = self.root / 'g'
        shutil.rmtree(f, ignore_errors=True)
        f.mkdir()
        (f / 'project.godot').write_text('config_version=5')
        for args in (['init', '-q'], ['config', 'user.email', 'a@b'], ['config', 'user.name', 'a']):
            core.run(['git', *args], f)
        p = f / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('x')
        return f

    def test_game_words_and_tool_dotfiles_are_committed(self):
        for rel in ('scripts/token_pickup.gd', 'scripts/secret_level.gd', 'ui/password_screen.gd',
                    '.editorconfig', '.metadata', '.gitattributes'):
            self.assertTrue(hp._commit(self.repo(rel), 't'), rel)

    def test_real_secrets_still_blocked(self):
        for rel in ('.env', '.env.local', '.npmrc', 'certs/server.pem', 'android/app/upload.jks',
                    'secrets/api.txt', 'android/key.properties', 'id_rsa'):
            with self.assertRaises(hp.UnsafeFiles, msg=rel):
                hp._commit(self.repo(rel), 't')

    def test_blocked_file_becomes_owner_question_not_a_lock(self):
        class AI(FakeAI):
            def __call__(self, role, prompt, cwd, dept, **kw):
                out = super().__call__(role, prompt, cwd, dept, **kw)
                if role == 'implement' and not (Path(cwd) / '.npmrc').exists():
                    (Path(cwd) / '.npmrc').write_text('_authToken=x')
                return out
        ai = AI(('PASS',) * 6)
        pid = self.started(ai)['id']
        p = hp.run_production(pid, self.db, ai=ai, tester=lambda f: (True, 'OK'))
        self.assertEqual(p['stage'], 'soru')
        self.assertEqual(p['packages'][0]['status'], 'kayit')
        q = hp.open_questions(self.db)[0]
        self.assertEqual(q['kind'], 'commit')
        self.assertIn('.npmrc', q['text'])
        calls = len(ai.calls)
        _, resume = hp.answer(q['id'], 'Bu dosyaları Git dışında bırak ve devam et', self.db)
        self.assertTrue(resume)
        folder = Path(p['folder'])
        self.assertTrue((folder / '.npmrc').exists())  # nothing deleted
        self.assertIn('/.npmrc', (folder / '.gitignore').read_text())
        self.assertEqual(hp.get(pid, self.db)['packages'][0]['status'], 'tamam')
        p = hp.run_production(pid, self.db, ai=ai, tester=lambda f: (True, 'OK'))
        self.assertEqual(p['stage'], 'teslim')
        self.assertEqual(len([c for c in ai.calls[calls:] if c[0] == 'implement']), 1)  # package 1 not redone
        self.assertNotIn('.npmrc', core.run(['git', 'ls-files'], folder).stdout)

    def test_default_gitignore_keeps_env_out_without_asking(self):
        class AI(FakeAI):
            def __call__(self, role, prompt, cwd, dept, **kw):
                if role == 'implement':
                    (Path(cwd) / '.env').write_text('API_KEY=x')
                return super().__call__(role, prompt, cwd, dept, **kw)
        ai = AI(('PASS',) * 6)
        p = hp.run_production(self.started(ai)['id'], self.db, ai=ai, tester=lambda f: (True, 'OK'))
        self.assertEqual(p['stage'], 'teslim')
        self.assertNotIn('.env', core.run(['git', 'ls-files'], Path(p['folder'])).stdout)

    def test_interrupted_commit_resumes_without_tokens(self):
        ai = FakeAI(('PASS',) * 6)
        pid = self.started(ai)['id']
        k = hp.get(pid, self.db)['packages'][0]
        (Path(hp.get(pid, self.db)['folder']) / 'done.js').write_text('//')
        hp._pkg(k['id'], self.db, status='kayit', summary='ok')
        n = len(ai.calls)
        hp.run_production(pid, self.db, ai=ai, tester=lambda f: (True, 'OK'))
        self.assertEqual(hp.get(pid, self.db)['packages'][0]['status'], 'tamam')
        self.assertEqual(len([c for c in ai.calls[n:] if c[1] in ('oyun', 'uygulama')]), 1)  # only package 2


class PreflightTests(Base):
    def test_single_provider_spends_no_calls(self):
        pid = self.started(FakeAI())['id']
        runner = mock.Mock()
        real = lambda role, prompt, cwd, dept, **kw: router.call(role, prompt, cwd, dept, runner=runner,
                                                                 have={'Claude': 'c'}, **kw)
        for _ in range(3):
            hp.run_production(pid, self.db, ai=real, tester=lambda f: (True, 'OK'), have={'Claude': 'c'})
            q = hp.open_questions(self.db)
            self.assertEqual(q[0]['kind'], 'qa')
            self.assertIn('Hiç çağrı harcanmadı', q[0]['text'])
            hp.answer(q[0]['id'], q[0]['options'][0], self.db)
        runner.assert_not_called()
        self.assertEqual(store.calls_used(path=self.db), 0)
        self.assertEqual(hp.get(pid, self.db)['packages'][0]['status'], 'bekliyor')

    def test_capacity_follows_reviewer_count(self):
        import hq_org
        self.assertEqual(hp.review_capacity(self.db, {'Claude': 1, 'Codex': 1}), '')
        hq_org.apply([{'op': 'set_workflow', 'field': 'reviews', 'value': 2}], path=self.db)
        self.assertIn('en az 3', hp.review_capacity(self.db, {'Claude': 1, 'Codex': 1}))


class CopyTests(Base):
    def test_existing_project_copy_keeps_models_audio_and_textures(self):
        original = core.create_project(self.root, 'Vadi', 'godot', 'x')
        assets = ['models/kale.glb', 'models/kale.glb.import', 'audio/muzik.mp3', 'tex/zemin.exr',
                  'models/agac.gltf', 'models/agac.bin', 'scenes/main.tscn']
        for a in assets:
            (original / a).parent.mkdir(parents=True, exist_ok=True)
            (original / a).write_bytes(b'\0' * 64)
        (original / 'tools.exe').write_bytes(b'MZ')
        p = hp.new_product('Vadi', 'oyun', self.db)
        hp._set(p['id'], self.db, spec='{"name":"Vadi","engine":"godot","summary":"x","features":["a","b"]}')
        copy = hp.prepare_folder(hp.get(p['id'], self.db), self.db, existing=str(original))
        for a in assets:
            self.assertTrue((copy / a).is_file(), a)
        self.assertFalse((copy / 'tools.exe').exists())  # executables are never copied


class RedirectTests(unittest.TestCase):
    def fake(self, routes):
        """routes: host -> (ip, status, location)."""
        def dns(host, port, type=None):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (routes[host][0], 443))]

        def conn_for(host, port, timeout=None):
            c = mock.Mock()
            _, status, loc = routes[host]
            c.getresponse.return_value = mock.Mock(status=status, getheader=lambda h: loc)
            return c
        return (mock.patch.object(research.socket, 'getaddrinfo', side_effect=dns),
                mock.patch.object(research.socket, 'create_connection', return_value=mock.Mock()),
                mock.patch.object(research.ssl, 'create_default_context', return_value=mock.Mock()),
                mock.patch.object(research.http.client, 'HTTPConnection', side_effect=conn_for))

    def run_with(self, routes, url):
        patches = self.fake(routes)
        with patches[0] as dns, patches[1] as dial, patches[2], patches[3]:
            return research.reachable(url), dns, dial

    def test_public_redirect_followed_with_fresh_check(self):
        ok, dns, _ = self.run_with({'a.example.org': ('8.8.8.8', 301, 'https://www.example.org/x'),
                                    'www.example.org': ('1.1.1.1', 200, '')}, 'https://a.example.org/x')
        self.assertTrue(ok)
        self.assertEqual([c.args[0] for c in dns.call_args_list], ['a.example.org', 'www.example.org'])

    def test_redirect_to_private_network_refused_without_dialing(self):
        ok, _, dial = self.run_with({'a.example.org': ('8.8.8.8', 302, 'https://intranet.example.org/'),
                                     'intranet.example.org': ('10.0.0.5', 200, '')}, 'https://a.example.org/')
        self.assertFalse(ok)
        self.assertEqual(dial.call_count, 1)  # never connected to 10.0.0.5

    def test_http_downgrade_and_loops_refused(self):
        self.assertFalse(self.run_with({'a.example.org': ('8.8.8.8', 301, 'http://a.example.org/')},
                                       'https://a.example.org/')[0])
        self.assertFalse(self.run_with({'a.example.org': ('8.8.8.8', 302, '/again')}, 'https://a.example.org/')[0])


if __name__ == '__main__':
    unittest.main()
