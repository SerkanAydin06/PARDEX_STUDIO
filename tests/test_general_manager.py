"""Manager regression tests. No external AI/network/engine called."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import core
import task_queue as q
import general_manager as gm

class ManagerTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root=Path(t.name)
        self.db=self.root/'private'/'q.sqlite3'
        self.project=self.root/'Project'
        self.project.mkdir()
        (self.project/'project.godot').write_text('config_version=5')
        patch=mock.patch.object(core,'STATE',self.root/'usage.json')
        patch.start();self.addCleanup(patch.stop)

    def test_offline_preview(self):
        with mock.patch.object(core,'run_ai_task') as ai:
            p=gm.preview(self.project,'Improve inventory menu','Basit')
            ai.assert_not_called()
        self.assertEqual(p['max_cli_calls'],1)
        self.assertEqual(gm.list_plans(self.db),[])

    def test_risk_budgets_and_persistence(self):
        for risk,n in [('Basit',1),('Normal',2),('Kritik',3)]:
            p=gm.create(self.project,'Build useful interface',risk=risk,path=self.db)
            self.assertEqual(len(p['tasks']),n)
            self.assertEqual(p['call_ceiling'],n)
            self.assertTrue(all(t['status']=='pending-owner' for t in p['tasks']))
        self.assertEqual(gm.dashboard(self.db)['estimated_max_cli_calls'],6)
        self.assertFalse(gm.dashboard(self.db)['subscription_remaining_tokens_known'])

    def test_dependencies_require_owner_acceptance(self):
        p=gm.create(self.project,'Improve camera controls',path=self.db)
        first,qa=p['tasks']
        q.approve(qa['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='found'):
            self.assertIsNone(q.claim_next(path=self.db))
        q.approve(first['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='found'):
            self.assertEqual(q.claim_next(path=self.db)['id'],first['id'])
        q._transition(first['id'],('running',),'awaiting-acceptance','finished',path=self.db,
                      fields={'verified':1,'handoff_note':'Checked controller tests'})
        with mock.patch.object(core,'which',return_value='found'):
            self.assertIsNone(q.claim_next(path=self.db))
        q.accept(first['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='found'):
            self.assertEqual(q.claim_next(path=self.db)['id'],qa['id'])

    def test_failed_work_cannot_run_review(self):
        p=gm.create(self.project,'Improve camera controls',path=self.db)
        first,qa=p['tasks']
        q.approve(first['id'],path=self.db);q.approve(qa['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='fake'),mock.patch.object(core,'run_ai_task',return_value={'ai_ok':True,'verified':False}):
            q.execute_one(path=self.db)
        with mock.patch.object(core,'which',return_value='fake'):
            self.assertIsNone(q.claim_next(path=self.db))
        self.assertEqual(gm.get(p['id'],self.db)['status'],'needs-attention')

    def test_cross_project_dependency_rejected(self):
        other=self.root/'Other';other.mkdir()
        (other/'index.html').write_text('<html></html>')
        a=q.add_task(self.project,'Make a better UI',path=self.db)
        with self.assertRaises(ValueError):
            q.add_task(other,'Review the other UI',path=self.db,depends_on=[a['id']])

    def test_handoff_only_after_acceptance(self):
        a=q.add_task(self.project,'Implement screen changes',path=self.db)
        b=q.add_task(self.project,'Review screen changes',kind='Inceleme / Analiz',path=self.db,depends_on=[a['id']])
        q.approve(a['id'],path=self.db);q.approve(b['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='fake'),mock.patch.object(core,'run_ai_task',return_value={
           'ai_ok':True,'verified':True,'output':'Updated UI anchors','provider':'Codex','model':'default'}):
            q.execute_one(path=self.db)
        q.accept(a['id'],path=self.db)
        with mock.patch.object(core,'which',return_value='fake'),mock.patch.object(core,'run_ai_task',return_value={
           'ai_ok':True,'verified':True,'output':'QA done','provider':'Gemini','model':'auto'}) as ai:
            q.execute_one(path=self.db)
        self.assertIn('Updated UI anchors',ai.call_args.kwargs['context_note'])

    def test_validation(self):
        with self.assertRaises(ValueError):gm.preview(self.project,'short')
        with self.assertRaises(ValueError):gm.preview(self.project,'Important task','infinite')
        with self.assertRaises(ValueError):gm.create(self.project,'Important task',priority=99,path=self.db)
        a=q.add_task(self.project,'Create menu controls',path=self.db)
        with self.assertRaises(ValueError):q.add_task(self.project,'Review menu controls',depends_on=[a['id'],a['id']],path=self.db)
        self.assertEqual(len(q.list_tasks(self.db)),1)

if __name__=='__main__':unittest.main()
