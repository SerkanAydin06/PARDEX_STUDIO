"""Phase 2C measurement tests: never call a real model."""
import tempfile, unittest, sys
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import core
import task_queue as q
import performance
import general_manager as gm

class PerformanceTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.db=self.root/'task.sqlite3'
        self.proj=self.root/'Godot';self.proj.mkdir()
        (self.proj/'project.godot').write_text('config_version=5')
        p=mock.patch.object(core,'STATE',self.root/'other.json')
        p.start();self.addCleanup(p.stop)
    def run_task(self,ai_ok=True,verified=True):
        t=q.add_task(self.proj,'Create a visible game menu',provider='Codex',path=self.db)
        q.approve(t['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='fake'),mock.patch.object(core,'run_ai_task',return_value={
                'ai_ok':ai_ok,'verified':verified,'provider':'Codex','model':'cli-default'}):
            finished=q.execute_one(path=self.db)
        return finished
    def test_empty_report_is_free(self):
        with mock.patch.object(core,'run_ai_task') as call:
            self.assertEqual(performance.report(self.db)['total_attempts'],0)
            self.assertEqual(performance.recommendations(self.db),[])
            call.assert_not_called()
    def test_verified_not_owner_accepted(self):
        t=self.run_task()
        d=performance.report(self.db)['by_provider_and_kind'][0]
        self.assertEqual((d['verified'],d['owner_accepted'],d['awaiting_review']),(1,0,1))
        q.accept(t['id'],path=self.db)
        d=performance.report(self.db)['by_provider_and_kind'][0]
        self.assertEqual((d['owner_accepted'],d['acceptance_rate_reviewed']),(1,1.0))
    def test_owner_rejection(self):
        t=self.run_task()
        q.request_rework(t['id'],'UI alignment is broken',path=self.db)
        self.assertEqual(performance.report(self.db)['by_provider_and_kind'][0]['owner_rejected'],1)
    def test_ai_failure_and_test_failure(self):
        self.run_task(ai_ok=False,verified=False)
        self.run_task(ai_ok=True,verified=False)
        with q._conn(self.db) as db:
            codes={r[0] for r in db.execute('SELECT result_code FROM task_attempt_metrics')}
        self.assertEqual(codes,{'ai_failed','test_failed'})
    def test_failed_retry_is_preserved(self):
        t=self.run_task(ai_ok=False,verified=False)
        q.reset_for_manual_retry(t['id'],path=self.db)
        q.approve(t['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='fake'),mock.patch.object(core,'run_ai_task',return_value={
                'ai_ok':True,'verified':True,'provider':'Codex','model':'default'}):
            finished=q.execute_one(path=self.db)
        q.accept(finished['id'],path=self.db)
        with q._conn(self.db) as db:
            codes=[r[0] for r in db.execute('SELECT result_code FROM task_attempt_metrics ORDER BY attempt')]
        self.assertEqual(codes,['ai_failed','verified'])
    def test_no_fake_cost_or_unreviewed_recommendation(self):
        self.run_task()
        report=performance.report(self.db)
        self.assertFalse(report['actual_cloud_token_usage_known'])
        self.assertFalse(report['subscription_balance_known'])
        self.assertFalse(gm.dashboard(self.db)['observed_execution_metrics']['provider_prices_known'])
        self.assertEqual(performance.recommendations(self.db),[])
        with self.assertRaises(ValueError):performance.recommendations(self.db,minimum_reviewed=2)
    def test_metrics_do_not_store_user_prompt(self):
        self.run_task()
        with q._conn(self.db) as db:
            raw=str(dict(db.execute('SELECT * FROM task_attempt_metrics').fetchone()))
        self.assertNotIn('Create a visible game menu',raw)

if __name__=='__main__':unittest.main()
