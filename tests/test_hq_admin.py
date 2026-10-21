"""Owner administration regression: real SQLite/files, no AI or network."""
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import core
import hq_admin as admin
import hq_projects as projects
import hq_store as store
import task_queue


class AdminTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / 'company.sqlite3'
        self.queue = self.root / 'queue.sqlite3'
        qp = patch.object(task_queue, 'DATABASE', self.queue)
        qp.start(); self.addCleanup(qp.stop)
        self.products = self.root / 'products'
        self.products.mkdir()
        patcher = patch.object(core, 'STATE', self.root / 'state.json')
        patcher.start(); self.addCleanup(patcher.stop)
        self.godot = self.root / 'Godot-test.exe'
        self.godot.touch()
        store.update_settings({'projects_root': str(self.products), 'godot_path': str(self.godot)}, self.db)
        self.p = projects.new_product('Deneme', 'oyun', self.db)
        self.folder = self.products / 'deneme'
        self.folder.mkdir()
        (self.folder / "project.godot").write_text("config_version=5", encoding="utf-8")
        projects._mark(self.folder, self.p['id'])
        (self.folder / 'source.txt').write_text('original', encoding='utf-8')
        with projects._Tx(self.db) as db:
            db.execute('UPDATE products SET folder=? WHERE id=?', (str(self.folder), self.p['id']))

    def test_list_remove_restore(self):
        admin.remove(self.p['id'], 'Deneme', path=self.db)
        self.assertTrue(self.folder.is_dir())
        self.assertEqual(projects.products(self.db), [])
        self.assertEqual(len(admin.trash(self.db)), 1)
        admin.restore(self.p['id'], self.db)
        self.assertEqual(projects.get(self.p['id'], self.db)['chat'], self.p['chat'])

    def test_file_remove_restore(self):
        admin.remove(self.p['id'], 'Deneme', True, self.db)
        self.assertFalse(self.folder.exists())
        moved = Path(admin.trash(self.db)[0]['moved'])
        self.assertEqual((moved / 'source.txt').read_text(), 'original')
        admin.restore(self.p['id'], self.db)
        self.assertEqual((self.folder / 'source.txt').read_text(), 'original')
        self.assertEqual(admin.trash(self.db), [])

    def test_restore_conflict_preserves_trash(self):
        admin.remove(self.p['id'], 'Deneme', True, self.db)
        self.folder.mkdir()
        with self.assertRaises(ValueError):
            admin.restore(self.p['id'], self.db)
        self.assertEqual(len(admin.trash(self.db)), 1)
        self.assertEqual(projects.products(self.db), [])

    def test_confirm_and_foreign_marker(self):
        with self.assertRaises(ValueError):
            admin.remove(self.p['id'], '', True, self.db)
        projects._mark(self.folder, 'foreign')
        with self.assertRaises(ValueError):
            admin.remove(self.p['id'], 'Deneme', True, self.db)
        self.assertTrue(self.folder.exists())
        self.assertEqual(len(projects.products(self.db)), 1)

    def test_rename_failure_keeps_records(self):
        with patch.object(Path, 'rename', side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError):
                admin.remove(self.p['id'], 'Deneme', True, self.db)
        self.assertEqual(len(projects.products(self.db)), 1)
        self.assertEqual(admin.trash(self.db), [])

    def test_reset_daily_preserves_usage_and_subsequent_calls(self):
        core.record_usage('Gemini'); core.record_usage('Codex')
        self.assertEqual(core.reset_daily_usage()['previous'], 2)
        self.assertEqual(core.usage_count(), 0)
        core.record_usage('Gemini')
        self.assertEqual(core.usage_count(), 1)
        self.assertEqual(core.usage_count('Gemini'), 1)
        self.assertEqual(core.state()['days'][core.today()]['Gemini'], 2)
        core.reset_daily_usage()
        self.assertEqual(core.usage_count(), 0)
        self.assertEqual(len(core.state()['usage_resets']), 2)

    def test_company_reset_backup_preserves_files_and_counter(self):
        task_queue.add_task(str(self.folder), 'Test task', path=self.queue)
        core.record_usage('Gemini')
        result = admin.reset_company('SIFIRLA', self.db, self.queue)
        self.assertEqual(projects.products(self.db), [])
        self.assertTrue(self.folder.exists())
        self.assertEqual(core.usage_count(), 1)
        self.assertEqual(store.settings(self.db)['godot_path'], str(self.godot))
        self.assertTrue(store.settings(self.db)['paused'])
        with closing(sqlite3.connect(Path(result['backup']) / 'company.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM products').fetchone()[0], 1)
        with task_queue._conn(self.queue) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM tasks').fetchone()[0], 0)

    def test_company_reset_rejects_running_queue_and_wrong_confirmation(self):
        with self.assertRaises(ValueError):
            admin.reset_company('', self.db, self.queue)
        t = task_queue.add_task(str(self.folder), 'Test task', path=self.queue)
        with task_queue._conn(self.queue) as db:
            db.execute("UPDATE tasks SET status='running'")
        with self.assertRaises(ValueError):
            admin.reset_company('SIFIRLA', self.db, self.queue)
        self.assertEqual(len(projects.products(self.db)), 1)

    def test_company_reset_keeps_project_trash(self):
        admin.remove(self.p['id'], 'Deneme', True, self.db)
        admin.reset_company('SIFIRLA', self.db, self.queue)
        admin.restore(self.p['id'], self.db)
        self.assertTrue(self.folder.exists())

    def test_remove_cancels_pending_queue_without_auto_resume(self):
        task_queue.add_task(str(self.folder), 'Test task', path=self.queue)
        admin.remove(self.p['id'], 'Deneme', path=self.db)
        admin.restore(self.p['id'], self.db)
        with task_queue._conn(self.queue) as db:
            self.assertEqual(db.execute('SELECT status FROM tasks').fetchone()[0], 'cancelled')

    def test_admin_http_auth_busy_and_confirmation(self):
        import threading
        import urllib.request
        import urllib.error
        import hq_server
        from http.server import ThreadingHTTPServer
        panel = hq_server.Panel(db=self.db, queue_db=self.queue, token='admin-test')
        server = ThreadingHTTPServer(('127.0.0.1', 0), hq_server.make_handler(panel))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        def post(path, data, token='admin-test'):
            req = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + path,
                data=json.dumps(data).encode(), headers={'X-PARDEX-Token': token, 'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=3) as response:
                    return response.status
            except urllib.error.HTTPError as e:
                return e.code
        body = {'confirmation': 'SIFIRLA'}
        self.assertEqual(post('/api/admin/company-reset', body, 'bad'), 403)
        panel.prod_state['running'] = self.p['id']
        self.assertEqual(post('/api/admin/company-reset', body), 400)
        self.assertEqual(post('/api/admin/day-reset', body), 400)
        panel.prod_state['running'] = ''
        self.assertEqual(post('/api/admin/company-reset', {}), 400)
        core.record_usage('Gemini')
        self.assertEqual(post('/api/admin/day-reset', body), 200)
        self.assertEqual(core.usage_count(), 0)
        self.assertEqual(len(projects.products(self.db)), 1)
