"""Phase 2E offline safety/measurement tests; no API keys, CLI calls or network."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import core
import task_queue as q
import worker_guard as wg
import benchmark_lab as lab
import usage_receipts as usage
import performance

def event(a=90,b=20,c=10):
    return json.dumps({'type':'turn.completed','usage':{'input_tokens':a,
                       'cached_input_tokens':b,'output_tokens':c}})

class Phase2ETests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.home=Path(tmp.name);self.db=self.home/'private'/'queue.sqlite3'
        self.project=self.home/'Game';self.project.mkdir()
        (self.project/'project.godot').write_text('config_version=5')
        p=mock.patch.object(core,'STATE',self.home/'usage.json');p.start();self.addCleanup(p.stop)

    def test_default_never_claims_isolation(self):
        self.assertFalse(wg.guard_native_agent(env={})['os_isolated'])

    def test_strict_mode_blocks_native_cli(self):
        with self.assertRaises(RuntimeError):
            wg.guard_native_agent(env={'PARDEX_REQUIRE_ISOLATED_AI':'1'})

    def test_strict_queue_keeps_task_ready_and_no_billing(self):
        task=q.add_task(self.project,'Create a settings menu',path=self.db)
        q.approve(task['id'],path=self.db)
        with mock.patch.dict('os.environ',{'PARDEX_REQUIRE_ISOLATED_AI':'1'}),mock.patch.object(core,'which',return_value='fake'),mock.patch.object(core,'run_ai_task') as agent:
            with self.assertRaises(RuntimeError):q.execute_one(path=self.db)
        agent.assert_not_called()
        with q._conn(self.db) as db:
            self.assertEqual(db.execute('SELECT status FROM tasks WHERE id=?',(task['id'],)).fetchone()[0],'ready')
        self.assertEqual(core.usage_count(),0)

    def test_direct_model_call_blocked(self):
        with mock.patch.dict('os.environ',{'PARDEX_REQUIRE_ISOLATED_AI':'1'}),mock.patch.object(core,'which',return_value='fake'),mock.patch.object(core,'run') as runner:
            with self.assertRaises(RuntimeError):core.run_ai_task(self.project,'Yeni ozellik / Kod','Add menu')
        runner.assert_not_called()

    def test_private_memory_excluded_in_fingerprint(self):
        a=self.home/'Another';a.mkdir()
        (a/'project.godot').write_text('config_version=5')
        for folder in [self.project,a]:
            (folder/'.studio').mkdir()
            (folder/'.studio'/'BRIEF.md').write_text('PRIVATE SECRET '+str(folder))
        self.assertEqual(lab.fingerprint(self.project)['fingerprint'],lab.fingerprint(a)['fingerprint'])
        self.assertTrue(lab.comparable(lab.fingerprint(self.project),lab.fingerprint(a),
                        'same task','same task','unit','unit','Godot 4.5','Godot 4.5')['ready_for_owner_approved_pilot'])
        self.assertFalse(lab.comparable(lab.fingerprint(self.project),lab.fingerprint(a),
                        'different','same','unit','unit','Godot 4.5','Godot 4.5')['ready_for_owner_approved_pilot'])

    def test_reported_codex_usage_is_not_billing(self):
        t=q.add_task(self.project,'Write working game flow',path=self.db)
        with q._conn(self.db) as db:
            db.execute('''INSERT INTO task_attempt_metrics(task_id,attempt,project,kind,provider,model,started_at,result_code)
                          VALUES(?,?,?,?,?,?,?,?)''',
                       (t['id'],1,str(self.project),'Yeni ozellik / Kod','Codex','local','now','verified'))
        with self.assertRaises(PermissionError):
            usage.import_codex_usage(t['id'],1,event(),path=self.db)
        result=usage.import_codex_usage(t['id'],1,event(),path=self.db,owner_confirms_source=True)
        self.assertFalse(result['verified_billing'])
        self.assertEqual(performance.report(self.db)['provider_reported_usage']['tokens']['input'],90)
        self.assertFalse(performance.report(self.db)['actual_cloud_token_usage_known'])

    def test_invalid_token_counts_rejected(self):
        for line in ('bad',event(2,9,1),json.dumps({'type':'turn.completed','usage':{'input_tokens':True,'cached_input_tokens':0,'output_tokens':1}})):
            with self.assertRaises(ValueError):usage.parse_codex_jsonl(line)

    def test_duplicate_import_refused(self):
        t=q.add_task(self.project,'Create sample game assets',path=self.db)
        with q._conn(self.db) as db:
            db.execute('''INSERT INTO task_attempt_metrics(task_id,attempt,project,kind,provider,model,started_at,result_code)
                          VALUES(?,?,?,?,?,?,?,?)''',(t['id'],1,str(self.project),'Yeni ozellik / Kod','Codex','local','now','verified'))
        usage.import_codex_usage(t['id'],1,event(),path=self.db,owner_confirms_source=True)
        with self.assertRaises(Exception):
            usage.import_codex_usage(t['id'],1,event(),path=self.db,owner_confirms_source=True)

if __name__=='__main__':unittest.main()
