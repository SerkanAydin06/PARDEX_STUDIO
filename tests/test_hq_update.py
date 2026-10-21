import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import hq_update as update
import hq_update_supervisor as supervisor
import hq_server
import core


class Checkout(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'checkout'
        self.root.mkdir()
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.root / 'version.txt').write_text('old')
        self.git('add', '.')
        self.git('commit', '-m', 'old')
        self.old = self.git('rev-parse', 'HEAD')
        (self.root / 'version.txt').write_text('new')
        self.git('commit', '-am', 'new')
        self.new = self.git('rev-parse', 'HEAD')
        self.git('checkout', 'main')
        self.git('reset', '--hard', self.old)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.DEVNULL, text=True).strip()

    def plan(self):
        job = self.base / 'updates/release-test'
        job.mkdir(parents=True)
        db = self.base / 'company.sqlite3'
        with closing(sqlite3.connect(db)) as con:
            con.execute('create table work (value text)')
            con.execute("insert into work values ('preserved')")
            con.commit()
        return {'root': str(self.root), 'old': self.old, 'target': self.new, 'job': str(job),
                'databases': [str(db)], 'nonce': 'test', 'port': 8765, 'python': sys.executable}

    def test_dirty_or_non_main_checkout_refused(self):
        self.assertEqual(update.clean_checkout(self.root), self.old)
        (self.root / 'local.txt').write_text('owner work')
        with self.assertRaises(ValueError):
            update.clean_checkout(self.root)
        (self.root / 'local.txt').unlink()
        self.git('checkout', '-b', 'work')
        with self.assertRaises(ValueError):
            update.clean_checkout(self.root)

    def test_successful_install_preserves_database(self):
        plan = self.plan()
        child = mock.Mock()
        child.poll.return_value = None
        self.assertTrue(supervisor.install(plan, starter=mock.Mock(return_value=child), checker=lambda *a: True))
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.new)
        self.assertTrue((Path(plan['job']) / 'database-0.sqlite3').is_file())
        child.terminate.assert_not_called()

    def test_failed_startup_restores_code_and_database(self):
        plan = self.plan()
        child = mock.Mock()
        child.poll.return_value = None
        starter = mock.Mock(return_value=child)
        def broken(*args):
            with closing(sqlite3.connect(plan['databases'][0])) as con:
                con.execute("update work set value='new migration'")
                con.commit()
            return False
        self.assertFalse(supervisor.install(plan, starter=starter, checker=broken))
        self.assertEqual(self.git('rev-parse', 'HEAD'), self.old)
        with closing(sqlite3.connect(plan['databases'][0])) as con:
            self.assertEqual(con.execute('select value from work').fetchone()[0], 'preserved')
        starter.assert_called_with(plan, health=False)
        child.terminate.assert_called_once()

    def test_new_local_edits_are_never_reset_on_failure(self):
        plan = self.plan()
        child = mock.Mock()
        child.poll.return_value = None
        def broken(*args):
            (self.root / 'version.txt').write_text('owner edit')
            return False
        with self.assertRaises(RuntimeError):
            supervisor.install(plan, starter=mock.Mock(return_value=child), checker=broken)
        self.assertEqual((self.root / 'version.txt').read_text(), 'owner edit')

    def test_prepare_cannot_publish_unreviewed_candidate(self):
        import evolution
        with mock.patch.object(evolution, 'info', return_value={'source_revision': self.old}), \
             mock.patch.object(evolution, 'ready_to_export', return_value=False), \
             mock.patch.object(update, 'api') as api:
            with self.assertRaises(ValueError):
                update.publish(self.root, self.base, lambda m: None)
            api.assert_not_called()

    def test_publish_checks_pinned_head_before_merge(self):
        import evolution
        import hashlib
        candidate = self.base / 'candidate'
        (candidate / 'app').mkdir(parents=True)
        content = b'x = 1\n'
        (candidate / 'app/fix.py').write_bytes(content)
        manifest = {'source_revision': self.old, 'tests': {'hashes': {'app/fix.py': hashlib.sha256(content).hexdigest()}}}
        replies = [{'object': {'sha': self.old}}, {'tree': {'sha': 'tree'}}, {'sha': 'newtree'},
                   {'sha': self.new}, {}, {'number': 9, 'html_url': 'https://github.com/test/pull/9'},
                   {'object': {'sha': 'changed-main'}}]
        with mock.patch.object(evolution, 'info', return_value=manifest), \
             mock.patch.object(evolution, 'ready_to_export', return_value=True), \
             mock.patch.object(evolution, 'changed_files', return_value=[{'path': 'app/fix.py'}]), \
             mock.patch.object(update, 'wait_checks'), \
             mock.patch.object(update, 'api', side_effect=replies) as api:
            with self.assertRaisesRegex(ValueError, 'main değişti'):
                update.publish(self.root, candidate, lambda m: None)
            self.assertFalse(any('/merge' in c.args[1] for c in api.call_args_list))


class Checks(unittest.TestCase):
    def test_detached_real_panel_startup_and_health(self):
        import socket
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'app').mkdir()
            job = root / 'job'
            job.mkdir()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            actual_app = str(Path(hq_server.__file__).resolve().parent)
            # Thin launcher into the real panel, using isolated test databases.
            script = ('import sys\n' + 'sys.path.insert(0, ' + repr(actual_app) + ')\n'
                + 'from hq_server import serve, Panel\n'
                + 'serve(' + str(port) + ', False, Panel(db=' + repr(str(root / 'hq.db'))
                + ', queue_db=' + repr(str(root / 'queue.db')) + '))\n')
            (root / 'app/hq_server.py').write_text(script, encoding='utf-8')
            plan = {'root': str(root), 'job': str(job), 'nonce': 'real-panel-test',
                    'python': sys.executable, 'port': port}
            child = supervisor.start(plan)
            try:
                self.assertTrue(supervisor.healthy(plan, child, timeout=20),
                                (job / 'panel.log').read_text(encoding='utf-8', errors='replace'))
            finally:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=10)

    def test_parent_process_check_does_not_terminate_processes(self):
        self.assertTrue(supervisor.parent_alive(os.getpid()))
        child = subprocess.Popen([sys.executable, '-c', 'pass'])
        child.wait(timeout=10)
        self.assertFalse(supervisor.parent_alive(child.pid))

    def test_missing_failed_or_untrusted_checks_never_pass(self):
        sha = 'a' * 40
        rows = [{'name': n, 'app': {'slug': 'github-actions'}, 'status': 'completed', 'conclusion': 'success'} for n in update.REQUIRED]
        with mock.patch.object(update, 'api', return_value={'check_runs': rows}):
            self.assertTrue(update.checked('.', sha))
        with mock.patch.object(update, 'api', return_value={'check_runs': rows[:1]}):
            self.assertFalse(update.checked('.', sha))
        rows[0]['conclusion'] = 'failure'
        with mock.patch.object(update, 'api', return_value={'check_runs': rows}):
            with self.assertRaises(ValueError):
                update.checked('.', sha)
        rows[0]['conclusion'] = 'success'
        rows[0]['app']['slug'] = 'unknown'
        with mock.patch.object(update, 'api', return_value={'check_runs': rows}):
            self.assertFalse(update.checked('.', sha))

    def test_wait_cancel_does_not_touch_files_or_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller = update.Controller(tmp, tmp)
            stop = mock.Mock()
            with mock.patch.object(update, 'prepare') as prepare:
                thread = controller.begin(lambda: True, stop, 8765, [])
                controller.cancel_wait()
                thread.join(3)
                self.assertFalse(thread.is_alive())
                prepare.assert_not_called()
                stop.assert_not_called()
                self.assertFalse(controller.busy())

    def test_busy_work_finishes_before_prepare_and_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            controller = update.Controller(tmp, tmp)
            working = threading.Event()
            working.set()
            with mock.patch.object(update, 'prepare', return_value={'test': 'plan'}) as prepare, \
                 mock.patch.object(update, 'launch') as launch:
                shutdown = mock.Mock()
                thread = controller.begin(working.is_set, shutdown, 8765, [])
                prepare.assert_not_called()
                working.clear()
                thread.join(3)
                self.assertFalse(thread.is_alive())
                prepare.assert_called_once()
                launch.assert_called_once()
                shutdown.assert_called_once()

    def test_health_rejects_wrong_nonce_and_dead_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'healthy.json').write_text(json.dumps({'nonce': 'wrong', 'pid': 4}))
            child = mock.Mock(pid=4)
            child.poll.return_value = None
            self.assertFalse(supervisor.healthy({'job': tmp, 'nonce': 'right', 'port': 1}, child, timeout=.01))
            child.poll.return_value = 1
            self.assertFalse(supervisor.healthy({'job': tmp}, child))

    def test_github_login_uses_official_cli_not_copilot(self):
        import hq_setup
        with mock.patch.object(core, 'which', return_value='gh'):
            self.assertEqual(hq_setup.login_command('gh'), ['gh', 'auth', 'login', '--hostname', 'github.com', '--git-protocol', 'https', '--web'])


class UpdateRoutes(unittest.TestCase):
    def test_auth_busy_and_candidate_gates(self):
        import urllib.request
        import urllib.error
        from http.server import ThreadingHTTPServer
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(core, 'HOME', Path(tmp)):
            panel = hq_server.Panel(db=Path(tmp) / 'hq.db', token='test-update-session')
            panel.update_async = mock.Mock()
            panel.updater = mock.Mock()
            panel.updater.busy.return_value = False
            server = ThreadingHTTPServer(('127.0.0.1', 0), hq_server.make_handler(panel))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            def post(path, token='test-update-session', body=None):
                request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}' + path,
                    data=json.dumps(body or {}).encode(), headers={'X-PARDEX-Token': token, 'Content-Type': 'application/json'})
                try:
                    with urllib.request.urlopen(request) as result:
                        return result.status
                except urllib.error.HTTPError as exc:
                    return exc.code
            try:
                self.assertEqual(post('/api/update', token='wrong'), 403)
                panel.update_async.assert_not_called()
                self.assertEqual(post('/api/update'), 200)
                panel.update_async.assert_called_once_with()
                panel.updater.busy.return_value = True
                self.assertEqual(post('/api/update'), 400)
                self.assertEqual(post('/api/goal', body={'text': 'must not run'}), 400)
                self.assertEqual(post('/api/update/cancel'), 200)
                panel.updater.cancel_wait.assert_called_once()
                panel.updater.busy.return_value = False
                with mock.patch.object(hq_server.board, 'core_get', return_value={'ready': False}):
                    self.assertEqual(post('/api/update/publish', body={'id': 'test'}), 400)
                self.assertEqual(panel.update_async.call_count, 1)
            finally:
                server.shutdown(); server.server_close(); thread.join(2)
