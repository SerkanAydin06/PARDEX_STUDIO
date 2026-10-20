"""2F tests are offline: no actual model, Docker or internet service runs."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
import core
import operations
import task_queue as q

class OperationsTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.db=self.root/'private'/'queue.db'
        self.a=self.root/'Alpha';self.b=self.root/'Beta'
        for project in (self.a,self.b):
            project.mkdir()
            (project/'project.godot').write_text('config_version=5')
        for name, replacement in ((core,'STATE'),):
            patch=mock.patch.object(name,replacement,self.root/'usage.json')
            patch.start();self.addCleanup(patch.stop)
        patch=mock.patch.object(core,'which',return_value='/bin/fake')
        patch.start();self.addCleanup(patch.stop)

    def task(self,project=None,priority=3, approved=True,depends_on=()):
        obj=q.add_task(project or self.a,'Build feature and test it',
                       provider='Codex',priority=priority,path=self.db,depends_on=depends_on)
        if approved:q.approve(obj['id'],path=self.db)
        return obj['id']

    def preview(self,**kwargs):
        return operations.preview_shift(path=self.db,**kwargs)

    def run_approved(self,**kwargs):
        planned=self.preview(**{k:kwargs[k] for k in ('day_limit','max_cli_calls','max_total_minutes') if k in kwargs})
        return operations.run_shift(path=self.db,owner_confirms=True,
            authorized_task_ids=[x['id'] for x in planned['tasks']],**kwargs)

    def test_requires_explicit_owner_start(self):
        self.task()
        with self.assertRaises(PermissionError):
            operations.run_shift(path=self.db)
        self.assertEqual(q.list_tasks(path=self.db)[0]['status'],'ready')

    def test_preview_never_invokes_model(self):
        self.task()
        with mock.patch.object(core,'run_ai_task') as agent:
            info=self.preview()
        self.assertEqual(info['planned_calls'],1)
        agent.assert_not_called()
        self.assertFalse(info['tokens_or_subscription_balance_known'])

    def test_only_preapproved_tasks(self):
        self.task(approved=False)
        self.assertFalse(self.preview()['tasks'])
        info=self.run_approved()
        self.assertEqual(info['executed'],[])

    def test_one_task_per_project(self):
        first=self.task(self.a,priority=5)
        self.task(self.a,priority=4)
        plan=self.preview(max_cli_calls=3)
        self.assertEqual([x['id'] for x in plan['tasks']],[first])
        self.assertIn('same project',plan['blocked_reason'])

    def test_two_projects_are_bounded(self):
        a=self.task(self.a,priority=5)
        b=self.task(self.b,priority=4)
        self.assertEqual([x['id'] for x in self.preview()['tasks']],[a,b])
        self.assertEqual(self.preview(max_cli_calls=1)['planned_calls'],1)

    def test_respects_time_and_daily_ceiling(self):
        a=self.task(self.a,priority=5)
        self.task(self.b,priority=4)
        self.assertEqual([x['id'] for x in self.preview(max_total_minutes=15)['tasks']],[a])
        with mock.patch.object(core,'usage_count',return_value=7):
            self.assertEqual(self.preview(day_limit=8)['planned_calls'],1)
            self.assertEqual(self.preview(day_limit=7)['planned_calls'],0)

    def test_depends_on_accepted_not_just_approved(self):
        a=self.task(self.a,priority=5)
        b=self.task(self.a,priority=5,depends_on=(a,))
        self.assertEqual([x['id'] for x in self.preview()['tasks']],[a])
        self.assertEqual(q.get_task(b,path=self.db)['status'],'ready')

    def test_strict_mode_fails_closed(self):
        self.task()
        with mock.patch.dict('os.environ',{'PARDEX_REQUIRE_ISOLATED_AI':'1'}):
            plan=self.preview()
            self.assertEqual(plan['planned_calls'],0)
            self.assertEqual(self.run_approved()['executed'],[])
        self.assertEqual(q.list_tasks(path=self.db)[0]['status'],'ready')

    def test_stop_if_queue_order_changed(self):
        a=self.task(self.a,priority=5)
        b=self.task(self.b,priority=4)
        original=q.preview_next
        order=[0]
        def changed(**kwargs):
            order[0]+=1
            result=original(**kwargs)
            if order[0]==1:result['id']='TASK-UNLISTED'
            return result
        with mock.patch.object(q,'preview_next',side_effect=changed),mock.patch.object(core,'run_ai_task') as agent:
            report=self.run_approved()
        agent.assert_not_called()
        self.assertFalse(report['executed'])
        self.assertIn('order changed',report['stop_reason'])
        self.assertEqual(q.get_task(a,path=self.db)['status'],'ready')

    def test_approved_shift_executes_two_independent_tasks_not_acceptance(self):
        a=self.task(self.a,priority=5)
        b=self.task(self.b,priority=4)
        outcome={'ai_ok':True,'verified':True,'provider':'Codex','model':'demo','output':'ok'}
        with mock.patch.object(core,'run_ai_task',return_value=outcome) as agent:
            result=self.run_approved()
        self.assertEqual(agent.call_count,2)
        self.assertEqual([x['id'] for x in result['executed']],[a,b])
        self.assertTrue(result['requires_result_acceptance'])
        self.assertFalse(result['any_tasks_auto_accepted'])
        self.assertEqual(q.get_task(a,path=self.db)['status'],'awaiting-acceptance')
        self.assertEqual(q.get_task(b,path=self.db)['status'],'awaiting-acceptance')

    def test_stop_on_failed_task_without_retry(self):
        a=self.task(self.a,priority=5)
        b=self.task(self.b,priority=4)
        with mock.patch.object(core,'run_ai_task',return_value={'ai_ok':False,'verified':False}) as agent:
            result=self.run_approved()
        self.assertEqual(agent.call_count,1)
        self.assertEqual(result['executed'][0]['id'],a)
        self.assertEqual(q.get_task(b,path=self.db)['status'],'ready')
        self.assertFalse(result['automatic_retry'])

    def test_board_groups_multiple_projects_without_paths_or_prompts(self):
        self.task(self.a,approved=False)
        self.task(self.b)
        data=operations.board(path=self.db)
        self.assertEqual(data['project_count'],2)
        self.assertEqual(data['total_tasks'],2)
        self.assertEqual({x['project_name'] for x in data['projects']},{'Alpha','Beta'})
        self.assertNotIn(str(self.root),str(data))
        self.assertNotIn('Build feature',str(data))

    def test_exact_task_allowlist_is_required(self):
        self.task()
        with self.assertRaises(PermissionError):
            operations.run_shift(path=self.db,owner_confirms=True,authorized_task_ids=['OTHER'])

    def test_limits_reject_bool_and_unbounded_requests(self):
        for values in ({'max_cli_calls':4},{'max_total_minutes':180},{'day_limit':True},{'max_cli_calls':False}):
            with self.assertRaises(ValueError):self.preview(**values)

if __name__=='__main__':unittest.main()
