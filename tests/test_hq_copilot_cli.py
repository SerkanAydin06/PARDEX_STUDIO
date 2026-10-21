"""GitHub Copilot Pro CLI: optional fourth AI provider, least privilege, no billing bypass."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
import core
import hq_org
import hq_projects as projects
import hq_router as router
import hq_store as store


class CopilotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / 'hq.db'
        patch = mock.patch.object(core, 'STATE', self.root / 'state.json')
        patch.start()
        self.addCleanup(patch.stop)

    def test_existing_default_roles_unchanged(self):
        have = {'Claude': 'claude', 'Codex': 'codex', 'Gemini': 'gemini', 'Copilot': 'copilot'}
        self.assertEqual(router.choose('plan_chat', path=self.db, have=have)[0], 'Claude')
        self.assertEqual(router.choose('implement', path=self.db, have=have)[0], 'Codex')
        self.assertEqual(router.choose('review', path=self.db, have=have)[0], 'Gemini')

    def test_copilot_is_fallback_writer_and_independent_reviewer(self):
        have = {'Codex': 'codex', 'Copilot': 'copilot'}
        self.assertEqual(router.choose('implement', path=self.db, have=have)[0], 'Codex')
        self.assertEqual(router.choose('review', avoid=('Codex',), path=self.db, have=have)[0], 'Copilot')
        self.assertEqual(projects.review_capacity(self.db, have), '')
        self.assertIn('Copilot', projects.review_capacity(self.db, {'Codex': 'codex'}))
        with self.assertRaises(RuntimeError):
            router.choose('review', avoid=('Copilot',), path=self.db, have={'Copilot': 'copilot'})

    def test_only_copilot_can_plan_and_write(self):
        have = {'Copilot': 'copilot'}
        for role in ('plan_chat', 'breakdown', 'architect', 'implement', 'fix', 'review', 'text'):
            self.assertEqual(router.choose(role, path=self.db, have=have)[0], 'Copilot')
        with self.assertRaises(RuntimeError):
            router.choose('research', path=self.db, have=have)

    def test_write_flags_scope_to_file_edits(self):
        cmd = router.build_cmd('Copilot', 'copilot', '', '', 'write')
        self.assertEqual(cmd[0], 'copilot')
        self.assertIn('--silent', cmd)
        self.assertIn('--no-ask-user', cmd)
        self.assertIn('--available-tools=view,glob,grep,edit,create,apply_patch', cmd)
        self.assertIn('--allow-tool=read,write', cmd)
        self.assertIn('--deny-tool=shell,url,memory', cmd)
        self.assertNotIn('--allow-all', cmd)
        self.assertNotIn('--yolo', cmd)
        self.assertNotIn('--trust-folder', cmd)
        self.assertNotIn('--model', cmd)
        self.assertNotIn('-p', cmd)  # Copilot must consume prompt via stdin

    def test_read_flags_cannot_write_run_shell_or_fetch(self):
        cmd = router.build_cmd('Copilot', 'copilot', '', '', 'read')
        joined = ' '.join(cmd)
        self.assertIn('--available-tools=view,glob,grep', cmd)
        self.assertIn('--allow-tool=read', cmd)
        self.assertNotIn('apply_patch', joined)
        self.assertNotIn('create,', joined)
        self.assertNotIn('edit,', joined)
        self.assertIn('--deny-tool=shell,url,memory', cmd)
        self.assertNotIn('--model', cmd)

    def test_model_pinned_only_when_owner_configures(self):
        cmd = router.build_cmd('Copilot', 'copilot', 'claude-sonnet-5.5', '', 'read')
        self.assertEqual(cmd[-2:], ['--model', 'claude-sonnet-5.5'])
        store.update_settings({'routing': {'review': {'provider': 'Copilot',
                                                       'model': 'claude-sonnet-5.5',
                                                       'effort': ''}}}, self.db)
        self.assertEqual(router.choose('review', path=self.db, have={'Copilot': 'copilot'})[0], 'Copilot')
        self.assertEqual(router.choose('review', path=self.db, have={'Copilot': 'copilot'})[1], 'claude-sonnet-5.5')

    def test_board_can_approve_copilot_routing(self):
        ops = [{'op': 'set_routing', 'role': 'review', 'provider': 'Copilot',
                'model': '', 'effort': ''}]
        validated = hq_org.validate(ops, path=self.db)
        self.assertEqual(validated[0]['provider'], 'Copilot')

    def test_optional_install_detection_and_tool_status(self):
        def which(name):
            return r'C:\Tools\copilot.cmd' if name == 'copilot' else None
        with mock.patch.object(core, 'which', side_effect=which):
            self.assertEqual(router.installed(), {'Copilot': r'C:\Tools\copilot.cmd'})
            self.assertEqual(core.tool_status()['Copilot CLI'], r'C:\Tools\copilot.cmd')

    def test_real_dispatch_writes_stdin_and_tracks_budget(self):
        captured = []
        class R:
            returncode = 0
            stdout = 'PARDEX_QA_VERDICT=PASS\nPARDEX_QA_FINDINGS=verified'
        def runner(args, cwd, **kwargs):
            captured.append((args, cwd, kwargs))
            return R()
        with mock.patch.object(router, 'worker_guard', create=True):
            with mock.patch('worker_guard.guard_native_agent', return_value={}):
                result = router.call('review', 'READ FILES ONLY', self.root, 'kalite',
                                     path=self.db, runner=runner, have={'Copilot': 'copilot'})
        self.assertTrue(result['ok'])
        self.assertEqual(result['provider'], 'Copilot')
        self.assertEqual(len(captured), 1)
        cmd, cwd, kwargs = captured[0]
        self.assertEqual(kwargs['input_data'], 'READ FILES ONLY')
        self.assertEqual(cwd, self.root)
        self.assertIn('--allow-tool=read', cmd)
        self.assertNotIn('-p', cmd)
        self.assertNotIn('GITHUB_TOKEN', kwargs['env'])
        self.assertNotIn('COPILOT_GITHUB_TOKEN', kwargs['env'])
        self.assertNotIn('COPILOT_PROVIDER_API_KEY', kwargs['env'])
        self.assertEqual(store.calls_used('kalite', path=self.db), 1)

    def test_copilot_respects_pause_before_running(self):
        runner = mock.Mock()
        store.update_settings({'paused': True}, self.db)
        with self.assertRaises(router.BudgetStop):
            router.call('review', 'verify', self.root, 'kalite', path=self.db,
                        runner=runner, have={'Copilot': 'copilot'})
        runner.assert_not_called()

if __name__ == '__main__':
    unittest.main()
