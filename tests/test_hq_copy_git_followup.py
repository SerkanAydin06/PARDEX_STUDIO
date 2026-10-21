"""HQ regression tests: file policy parity, complete Git lists and failure cleanup.

Deterministic offline cases: no AI calls, no network, only temporary directories.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import core
import hq_projects as hp
import hq_store as store
import project_delivery as delivery


class SafetyFollowupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / 'hq.sqlite3'
        state_patch = mock.patch.object(core, 'STATE', self.root / 'state.json')
        state_patch.start()
        self.addCleanup(state_patch.stop)
        store.update_settings({'projects_root': str(self.root / 'products')}, self.db)

    def make_product(self):
        p = hp.new_product('Pirate Ship', 'oyun', self.db)
        spec = {'name': 'Pirate Ship', 'kind': 'oyun', 'engine': 'godot',
                'summary': '2D ship', 'features': ['Move'], 'acceptance': ['Works']}
        hp._set(p['id'], self.db, spec=json.dumps(spec))
        return hp.get(p['id'], self.db)

    def source(self):
        return core.create_project(self.root, 'OriginalShip', 'godot', 'Ships')

    def test_game_scripts_survive_copy_and_shared_secret_policy(self):
        source = self.source()
        for name in ('token_pickup.gd', 'secret_level.gd', 'password_screen.gd'):
            (source / 'scenes' / name).write_text('extends Node2D\n', encoding='utf-8')
            self.assertFalse(hp._secret_path('scenes/' + name))
            self.assertFalse(delivery._private(name))
        for name in ('client_token.json', 'secret_credentials.json', 'password_cache.json',
                     'api_key_config.json', 'service-account.json'):
            (source / 'scenes' / name).write_text('{"secret":"not-for-ai"}', encoding='utf-8')
            self.assertTrue(hp._secret_path('scenes/' + name), name)
            self.assertTrue(delivery._private(name), name)
        for name in ('.metadata', '.editorconfig', '.gitattributes'):
            (source / name).write_text('sample', encoding='utf-8')
        product_copy = hp.prepare_folder(self.make_product(), self.db, existing=str(source))
        for name in ('token_pickup.gd', 'secret_level.gd', 'password_screen.gd'):
            self.assertTrue((product_copy / 'scenes' / name).is_file(), name)
        for name in ('client_token.json', 'secret_credentials.json', 'password_cache.json',
                     'api_key_config.json', 'service-account.json'):
            self.assertFalse((product_copy / 'scenes' / name).exists(), name)
        for name in ('.metadata', '.editorconfig', '.gitattributes'):
            self.assertTrue((product_copy / name).is_file(), name)

    def test_disk_error_removes_partial_copy_not_source(self):
        source = self.source()
        marker = source / 'scenes' / 'main.tscn'
        before = marker.read_bytes()

        def disk_full(src, *, target, **kwargs):
            (target / 'partial.txt').write_text('partial')
            raise OSError(28, 'No space left on device')

        with mock.patch.object(delivery, '_snapshot', side_effect=disk_full):
            with self.assertRaises(OSError):
                hp.prepare_folder(self.make_product(), self.db, existing=str(source))
        target_dir = self.root / 'products'
        self.assertFalse(any(target_dir.iterdir()))
        self.assertEqual(marker.read_bytes(), before)
        self.assertFalse((source / '.git').exists())

    def test_project_registration_failure_cleans_copy(self):
        source = self.source()
        with mock.patch.object(core, 'attach_project', side_effect=OSError('cannot write .studio')):
            with self.assertRaises(OSError):
                hp.prepare_folder(self.make_product(), self.db, existing=str(source))
        self.assertFalse(any((self.root / 'products').iterdir()))
        self.assertTrue((source / 'project.godot').exists())

    def test_false_commit_cannot_mark_package_done(self):
        p = self.make_product()
        package = {'seq': 1, 'title': 'Movement', 'id': 'K-123456789'}
        with mock.patch.object(hp, '_commit', return_value=False):
            self.assertFalse(hp._commit_package(p['id'], package, self.root, self.db))
        questions = hp.open_questions(self.db)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]['kind'], 'commit')
        self.assertIn('Git commit', questions[0]['text'])

    @unittest.skipUnless(shutil.which('git'), 'Git CLI not installed')
    def test_git_command_failure_does_not_report_success(self):
        source = self.source()
        for cmd in (('init', '-q'), ('config', 'user.name', 'PARDEX'),
                    ('config', 'user.email', 'test@pardex.invalid')):
            result = subprocess.run(['git', *cmd], cwd=str(source),
                                    capture_output=True, check=False)
            self.assertEqual(result.returncode, 0)
        original = hp._git

        def fail_commit(folder, *args, **kw):
            if args and args[0] == 'commit':
                return subprocess.CompletedProcess(args, 1, 'FAIL')
            return original(folder, *args, **kw)

        with mock.patch.object(hp, '_git', side_effect=fail_commit):
            with self.assertRaisesRegex(RuntimeError, 'commit başarısız'):
                hp._commit(source, 'bad commit')
        self.assertFalse((source / '.git' / 'refs' / 'heads' / 'main').exists())

    @unittest.skipUnless(shutil.which('git'), 'Git CLI not installed')
    def test_large_git_inventory_never_silently_truncated(self):
        source = self.root / 'many_files'
        source.mkdir()
        self.assertEqual(subprocess.run(['git', 'init', '-q'], cwd=str(source)).returncode, 0)
        count = 660
        for i in range(count):
            (source / ('asset_' + str(i).zfill(5) + '_abcdefghijklmnopqrstuvwxyz.txt')).write_text('ok')
        paths = hp._git_z_paths(source, 'ls-files', '--cached', '--others',
                                 '--exclude-standard', '-z')
        self.assertEqual(len(paths), count)
        self.assertGreater(len('\0'.join(paths)), 10_000)
        self.assertIn('asset_00659_abcdefghijklmnopqrstuvwxyz.txt', paths)

    @unittest.skipUnless(shutil.which('git'), 'Git CLI not installed')
    def test_git_inventory_too_large_fails_closed(self):
        source = self.root / 'too_many'
        source.mkdir()
        subprocess.run(['git', 'init', '-q'], cwd=str(source), check=True)
        (source / 'longfilename.txt').write_text('ok')
        with self.assertRaisesRegex(RuntimeError, 'eksik, çok büyük'):
            hp._git_z_paths(source, 'ls-files', '--others', '--exclude-standard', '-z',
                            limit=2)

    @unittest.skipUnless(shutil.which('git'), 'Git CLI not installed')
    def test_sensitive_config_added_by_ai_is_blocked_on_commit(self):
        source = self.source()
        subprocess.run(['git', 'init', '-q'], cwd=str(source), check=True)
        (source / 'client_token.json').write_text('{"token":"SECRET"}', encoding='utf-8')
        with self.assertRaises(hp.UnsafeFiles):
            hp._commit(source, 'unsafe')
        self.assertFalse((source / 'client_token.json').is_symlink())


if __name__ == '__main__':
    unittest.main()
