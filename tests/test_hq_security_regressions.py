"""Offline security regression tests for the Claude HQ features."""
import json
import shutil
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import core
import hq_ceo
import hq_projects as hp
import hq_research as research
import hq_router as router
import hq_store as store


class HQSecurityRegressionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.db = self.root / 'hq.sqlite3'
        p = mock.patch.object(core, 'STATE', self.root / 'state.json')
        p.start()
        self.addCleanup(p.stop)
        store.update_settings({'projects_root': str(self.root / 'workspace')}, self.db)

    def product(self, engine='godot'):
        p = hp.new_product('Pirate Game', 'oyun', self.db)
        spec = {'name': 'Pirate Game', 'kind': 'oyun', 'engine': engine,
                'summary': '2D ship', 'features': ['Ship movement'],
                'acceptance': ['Ship moves']}
        hp._set(p['id'], self.db, spec=json.dumps(spec))
        return hp.get(p['id'], self.db)

    def test_existing_project_uses_safe_copy(self):
        original = core.create_project(self.root, 'PirateGame', 'godot', 'Pirate ships')
        (original / 'scripts').mkdir()
        source = original / 'scripts' / 'ship.gd'
        source.write_text('extends Node2D\n', encoding='utf-8')
        (original / '.env').write_text('MY_SECRET=yes\n', encoding='utf-8')
        copy = hp.prepare_folder(self.product(), self.db, existing=str(original))
        self.assertNotEqual(original, copy)
        self.assertEqual(source.read_text(), 'extends Node2D\n')
        self.assertTrue((copy / 'scripts' / 'ship.gd').is_file())
        self.assertFalse((copy / '.env').exists())
        self.assertFalse((original / '.git').exists())
        (copy / 'scripts' / 'ship.gd').write_text('extends Control\n', encoding='utf-8')
        self.assertEqual(source.read_text(), 'extends Node2D\n')

    def test_target_nested_under_original_refused(self):
        original = core.create_project(self.root, 'PirateGame', 'godot', 'Pirate ships')
        store.update_settings({'projects_root': str(original / 'unsafe')}, self.db)
        with self.assertRaises(ValueError):
            hp.prepare_folder(self.product(), self.db, existing=str(original))

    @unittest.skipUnless(shutil.which('git'), 'git not installed')
    def test_sensitive_git_files_not_committed(self):
        folder = hp.prepare_folder(self.product(engine='web'), self.db)
        (folder / '.npmrc').write_text('_authToken=secret\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            hp._commit(folder, 'should fail')
        staged = core.run(['git', 'diff', '--cached', '--name-only'], folder).stdout
        self.assertNotIn('.npmrc', staged)

    def test_legacy_destructive_rollback_refused_before_answer(self):
        p = self.product()
        q = hp.ask(p['id'], 'stuck', 'Fail', ['Bu paketin değişikliklerini geri al ve atla'],
                   package_id='K-deadbeef0', path=self.db)
        with self.assertRaises(ValueError):
            hp.answer(q, 'Bu paketin değişikliklerini geri al ve atla', self.db)
        pending = [x for x in hp.get(p['id'], self.db)['questions'] if x['id'] == q][0]
        self.assertEqual(pending['status'], 'acik')

    def test_independent_reviewer_requires_other_provider(self):
        with self.assertRaisesRegex(RuntimeError, 'Bağımsız'):
            router.choose('review', avoid=('Gemini',), path=self.db, have={'Gemini': 'gemini'})
        self.assertEqual(router.choose('review', avoid=('Gemini',), path=self.db,
                         have={'Claude': 'claude', 'Gemini': 'gemini'})[0], 'Claude')

    def test_pirate_fantasy_allowed_piracy_blocked(self):
        self.assertNotEqual(hq_ceo.plan('Korsan gemisi oyunu oluştur')[0].get('status'), 'blocked')
        self.assertEqual(hq_ceo.plan('Crack ve keygen üret')[0].get('status'), 'blocked')
        self.assertEqual(hq_ceo.plan('Korsan yazılım indir')[0].get('status'), 'blocked')

    def test_ssrf_local_and_mixed_ip_rejected(self):
        for url in ('http://example.org/', 'https://127.0.0.1/', 'https://localhost/',
                    'https://user:pass@example.org/', 'https://example.org:8443/'):
            self.assertFalse(research.reachable(url))
        for ip in ('127.0.0.1', '10.0.0.5', '169.254.169.254', '::1'):
            info = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 443))]
            with mock.patch.object(research.socket, 'getaddrinfo', return_value=info):
                with mock.patch.object(research.socket, 'create_connection') as dial:
                    self.assertFalse(research.reachable('https://example.org/'))
                    dial.assert_not_called()
        mixed = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443)),
                 (socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.1', 443))]
        with mock.patch.object(research.socket, 'getaddrinfo', return_value=mixed):
            self.assertEqual(research._public_ips('example.org'), [])

    def test_no_redirect_and_dns_pinned_after_validation(self):
        info = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 443))]
        conn = mock.Mock()
        conn.getresponse.return_value = mock.Mock(status=302)
        ctx = mock.Mock()
        with mock.patch.object(research.socket, 'getaddrinfo', return_value=info) as dns, \
                mock.patch.object(research.socket, 'create_connection', return_value=mock.Mock()) as dial, \
                mock.patch.object(research.ssl, 'create_default_context', return_value=ctx), \
                mock.patch.object(research.http.client, 'HTTPConnection', return_value=conn):
            self.assertFalse(research.reachable('https://example.org/redirect'))
        dns.assert_called_once()
        dial.assert_called_once_with(('8.8.8.8', 443), timeout=7)
        self.assertEqual(conn.request.call_args.args[:2], ('HEAD', '/redirect'))


if __name__ == '__main__':
    unittest.main()
