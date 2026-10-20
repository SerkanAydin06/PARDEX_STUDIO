"""Headless no-network tests for the owner-controlled AI work queue."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'app'))
import core
import task_queue as q

class TaskQueueTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.project=self.root/'Game'
        self.project.mkdir()
        (self.project/'project.godot').write_text('config_version=5')
        self.db=self.root/'store'/'task_queue.sqlite3'
        state=mock.patch.object(core,'STATE',self.root/'state.json')
        state.start()
        self.addCleanup(state.stop)

    def add(self,**kwargs):
        return q.add_task(self.project,'Yeni kamera ekrani yap',path=self.db,**kwargs)

    def test_persistence_and_approval_gate(self):
        t=self.add()
        self.assertEqual(q.get_task(t['id'],path=self.db)['status'],'pending-owner')
        with mock.patch.object(core,'which',return_value='codex'):
            self.assertIsNone(q.claim_next(path=self.db))
        self.assertEqual(core.usage_count(),0)
        self.assertEqual(q.approve(t['id'],path=self.db)['status'],'ready')

    def test_reject_invalid_inputs(self):
        with self.assertRaises(ValueError):self.add(priority=12)
        with self.assertRaises(ValueError):self.add(max_minutes=50)
        with self.assertRaises(ValueError):self.add(kind='Unknown')
        with self.assertRaises(ValueError):q.add_task(self.root,'Hello queue',path=self.db)

    def test_single_worker(self):
        a=self.add();b=self.add()
        q.approve(a['id'],path=self.db);q.approve(b['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='codex'):
            taken=q.claim_next(path=self.db)
            self.assertIsNotNone(taken)
            with self.assertRaises(RuntimeError):q.claim_next(path=self.db)
        self.assertEqual(sum(t['status']=='running' for t in q.list_tasks(path=self.db)),1)

    def test_priority(self):
        a=self.add(priority=1);b=self.add(priority=5)
        q.approve(a['id'],path=self.db);q.approve(b['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='codex'):
            self.assertEqual(q.claim_next(path=self.db)['id'],b['id'])

    def test_missing_cli_does_not_spend_or_change_status(self):
        t=self.add();q.approve(t['id'],path=self.db)
        with mock.patch.object(core,'which',return_value=None):
            with self.assertRaises(RuntimeError):q.claim_next(path=self.db)
        self.assertEqual(q.get_task(t['id'],path=self.db)['status'],'ready')
        self.assertEqual(core.usage_count(),0)

    def test_daily_limit(self):
        t=self.add();q.approve(t['id'],path=self.db)
        core.record_usage('Codex')
        with mock.patch.object(core,'which',return_value='codex'):
            with self.assertRaises(RuntimeError):q.claim_next(day_limit=1,path=self.db)
        self.assertEqual(q.get_task(t['id'],path=self.db)['status'],'ready')

    def test_owner_acceptance(self):
        t=self.add();q.approve(t['id'],path=self.db)
        with self.assertRaises(ValueError):q.accept(t['id'],path=self.db)
        result={'ai_ok':True,'verified':True,'provider':'Codex','model':'cli-varsayilan'}
        with mock.patch.object(core,'which',return_value='codex'),mock.patch.object(core,'run_ai_task',return_value=result):
            done=q.execute_one(path=self.db)
        self.assertEqual(done['status'],'awaiting-acceptance')
        self.assertEqual(q.accept(t['id'],path=self.db)['status'],'accepted')
        self.assertEqual([x['action'] for x in q.events(t['id'],path=self.db)],
                         ['created','owner-approved','claimed','finished','owner-accepted'])

    def test_engine_not_verified_is_not_success(self):
        t=self.add();q.approve(t['id'],path=self.db)
        result={'ai_ok':True,'verified':False}
        with mock.patch.object(core,'which',return_value='codex'),mock.patch.object(core,'run_ai_task',return_value=result):
            failed=q.execute_one(path=self.db)
        self.assertEqual(failed['status'],'needs-attention')
        with self.assertRaises(ValueError):q.accept(t['id'],path=self.db)
        self.assertEqual(q.reset_for_manual_retry(t['id'],path=self.db)['status'],'pending-owner')

    def test_error_no_auto_retry(self):
        t=self.add();q.approve(t['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='codex'),mock.patch.object(core,'run_ai_task',side_effect=RuntimeError('oops')) as fake:
            result=q.execute_one(path=self.db)
            self.assertEqual(fake.call_count,1)
        self.assertEqual(result['attempts'],1)
        self.assertEqual(result['status'],'needs-attention')

    def test_manual_recovery_required(self):
        t=self.add();q.approve(t['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='codex'):q.claim_next(path=self.db)
        with self.assertRaises(PermissionError):q.recover_interrupted(t['id'],path=self.db)
        self.assertEqual(q.recover_interrupted(t['id'],confirm=True,path=self.db)['status'],'needs-attention')

    def test_owner_rework(self):
        t=self.add();q.approve(t['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='codex'),mock.patch.object(core,'run_ai_task',return_value={'ai_ok':True,'verified':True}):
            q.execute_one(path=self.db)
        self.assertEqual(q.request_rework(t['id'],'Kamera sallaniyor',path=self.db)['status'],'needs-attention')
        self.assertEqual(q.reset_for_manual_retry(t['id'],path=self.db)['status'],'pending-owner')

    def test_cancel(self):
        t=self.add()
        self.assertEqual(q.cancel(t['id'],path=self.db)['status'],'cancelled')
        with self.assertRaises(ValueError):q.approve(t['id'],path=self.db)

    def test_preview_is_zero_ai_call(self):
        t=self.add(provider='Claude');q.approve(t['id'],path=self.db)
        with mock.patch.object(core,'run_ai_task') as call,mock.patch.object(core,'which',return_value='claude'):
            preview=q.preview_next(path=self.db)
        call.assert_not_called()
        self.assertEqual(preview['provider_estimate'],'Claude')
        self.assertEqual(preview['estimated_cli_calls'],1)
        self.assertFalse(q.statistics(path=self.db)['real_token_usage_known'])

    def test_secret_redaction(self):
        t=q.add_task(self.project,'Check OPENAI_API_KEY=my_secrethere in docs',path=self.db)
        self.assertNotIn('my_secrethere',q.get_task(t['id'],path=self.db)['title'])
        q.approve(t['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='codex'),mock.patch.object(core,'run_ai_task',side_effect=RuntimeError('Bearer abcsecret')):q.execute_one(path=self.db)
        self.assertNotIn('abcsecret',q.get_task(t['id'],path=self.db)['result_note'])

if __name__=='__main__':unittest.main()
