"""Offline QA contract and matched-pilot tests. No real account/model calls."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import core
import task_queue as q
import general_manager as gm
import quality_manager as qa

PASS='Result\nPARDEX_QA_VERDICT=PASS\nPARDEX_QA_FINDINGS=Tests and changed files checked; no blocking issues found.'
FAIL='Result\nPARDEX_QA_VERDICT=FAIL\nPARDEX_QA_FINDINGS=Blocking permission or regression issue found.'

class QualityTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)
        self.db=self.root/'private'/'tasks.sqlite'
        self.project=self.root/'Game';self.project.mkdir()
        (self.project/'project.godot').write_text('config_version=5')
        self.other=self.root/'GameClone';self.other.mkdir()
        (self.other/'project.godot').write_text('config_version=5')
        s=mock.patch.object(core,'STATE',self.root/'usage.json')
        s.start();self.addCleanup(s.stop)

    def _execute(self,provider,output='',verified=True):
        with mock.patch.object(core,'which',return_value='mock-cli'),mock.patch.object(
            core,'run_ai_task',return_value={'provider':provider,'model':'mock',
            'ai_ok':True,'verified':verified,'output':output}):
            return q.execute_one(path=self.db)

    def _managed(self):
        plan=gm.create(self.project,'Build a robust achievements view',risk='Normal',path=self.db)
        code,review=plan['tasks']
        q.approve(code['id'],path=self.db)
        self._execute('Codex','Code finished')
        q.accept(code['id'],path=self.db)
        return code,review

    def test_plan_does_not_call_ai_and_records_independent_contract(self):
        with mock.patch.object(core,'run_ai_task') as cli:
            plan=gm.create(self.project,'Fix the achievement notification bug',risk='Normal',path=self.db)
            a,b=plan['tasks']
            r=qa.review_status(b['id'],self.db)
            self.assertTrue(r['independent_provider'])
            self.assertEqual(r['producer_task_id'],a['id'])
            self.assertFalse(r['quality_gate_passed'])
            cli.assert_not_called()

    def test_valid_pass_still_requires_owner(self):
        producer,review=self._managed()
        q.approve(review['id'],path=self.db)
        completed=self._execute('Gemini',PASS)
        self.assertEqual(completed['status'],'awaiting-acceptance')
        self.assertFalse(qa.review_status(review['id'],self.db)['quality_gate_passed'])
        q.accept(review['id'],path=self.db)
        self.assertTrue(qa.review_status(review['id'],self.db)['quality_gate_passed'])
        self.assertEqual(qa.review_dashboard(self.db)['quality_gates_passed'],1)

    def test_fail_review_never_passes(self):
        _,review=self._managed()
        q.approve(review['id'],path=self.db)
        result=self._execute('Gemini',FAIL)
        self.assertEqual(result['status'],'needs-attention')
        self.assertEqual(qa.review_status(review['id'],self.db)['verdict'],'FAIL')

    def test_missing_marker_fails_closed(self):
        _,review=self._managed()
        q.approve(review['id'],path=self.db)
        self.assertEqual(self._execute('Gemini','Everything is perfect')['status'],'needs-attention')
        self.assertEqual(qa.review_status(review['id'],self.db)['verdict'],'INCONCLUSIVE')

    def test_same_real_provider_cannot_self_review(self):
        _,review=self._managed()
        q.approve(review['id'],path=self.db)
        self.assertEqual(self._execute('Codex',PASS)['status'],'needs-attention')
        self.assertFalse(qa.review_status(review['id'],self.db)['quality_gate_passed'])

    def test_structured_claim_parser_rejects_duplicates(self):
        self.assertIsNone(qa._qa_result('PARDEX_QA_VERDICT=PASS'))
        self.assertIsNone(qa._qa_result(PASS+'\nPARDEX_QA_VERDICT=FAIL'))
        self.assertIsNone(qa._qa_result('PARDEX_QA_VERDICT=PASS\nPARDEX_QA_FINDINGS=no'))

    def test_regular_review_backward_compatible(self):
        t=q.add_task(self.project,'Independent manual review of the bug',kind='Inceleme / Analiz',
                     provider='Gemini',path=self.db)
        q.approve(t['id'],path=self.db)
        self.assertEqual(self._execute('Gemini','Legacy response')['status'],'awaiting-acceptance')

    def test_stale_attempt_cannot_pass_gate(self):
        maker,review=self._managed()
        q.approve(review['id'],path=self.db)
        self._execute('Gemini',PASS)
        q.accept(review['id'],path=self.db)
        with q._conn(self.db) as c:
            c.execute('UPDATE tasks SET attempts=attempts+1 WHERE id=?',(maker['id'],))
        self.assertFalse(qa.review_status(review['id'],self.db)['quality_gate_passed'])

    def test_pilot_planning_is_free(self):
        with mock.patch.object(core,'run_ai_task') as cli:
            plan=qa.register_pilot('Hata duzeltme','Repair the broken camera movement',
                                   'godot','headless import',path=self.db)
            self.assertEqual(plan['paired_trials'],0)
            self.assertFalse(plan['actual_tokens_known'])
            self.assertFalse(plan['automatic_model_switch'])
            cli.assert_not_called()

    def test_pilot_requires_owner_attestation(self):
        p=qa.register_pilot('Hata duzeltme','Repair the broken camera movement',
                            'godot','headless import',path=self.db)
        with self.assertRaises(PermissionError):
            qa.record_pilot_trial(p['id'],1,'TASK-missing',path=self.db)

    def _finished(self,project,provider,title,accepted=True):
        item=q.add_task(project,title,kind='Hata duzeltme',provider=provider,path=self.db)
        q.approve(item['id'],path=self.db)
        self._execute(provider,'Done')
        if accepted:q.accept(item['id'],path=self.db)
        else:q.request_rework(item['id'],'Owner found a regression',path=self.db)
        return item

    def test_matched_pair_uses_real_tasks_and_keeps_unproven_note(self):
        scenario='Repair the broken camera movement'
        plan=qa.register_pilot('Hata duzeltme',scenario,'godot','headless import',path=self.db)
        first=self._finished(self.project,'Codex',scenario)
        qa.record_pilot_trial(plan['id'],1,first['id'],owner_confirms_isolation=True,path=self.db)
        second=self._finished(self.other,'Gemini',scenario,accepted=False)
        report=qa.record_pilot_trial(plan['id'],1,second['id'],
                                     owner_confirms_isolation=True,path=self.db)
        self.assertEqual(report['paired_trials'],1)
        self.assertFalse(report['fair_quality_comparison_ready'])
        self.assertFalse(report['cost_savings_proven'])
        self.assertEqual(len(qa.list_pilots(self.db)),1)

    def test_mismatched_scenario_rejected(self):
        plan=qa.register_pilot('Hata duzeltme','Repair the broken camera movement',
                               'godot','headless import',path=self.db)
        task=self._finished(self.project,'Codex','Repair the camera movement with another feature')
        with self.assertRaises(ValueError):
            qa.record_pilot_trial(plan['id'],1,task['id'],
                                  owner_confirms_isolation=True,path=self.db)

if __name__=='__main__':unittest.main()
